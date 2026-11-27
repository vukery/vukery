"""Testing a vukery game: RSpec-style specs on virtual time.

In a game's ``tests/``::

    import pytest
    from vukery.testing import GameRig, expect

    @pytest.fixture
    def game():
        rig = GameRig(Path(__file__).parents[1])   # the game folder
        yield rig
        rig.stop()

    def describe_base_mode():
        def it_scores_the_target(game):
            game.start_game()
            game.switch("s_target")
            expect(game.player.score).to_equal(1000)

The game runs in the ``test`` environment on a virtual clock: nothing
happens until the test does something, and ``advance()`` jumps time forward
instantly.

One verb per concept (no combined helpers): ``switch()`` changes switches,
``advance()`` moves time. "Hold a switch for 2 seconds" is two calls::

    game.switch("s_hole", state="active")
    game.advance(2)
"""

import asyncio
from pathlib import Path
from typing import Any

from vukery.core.clock import VirtualClock, settle
from vukery.core.errors import ConfigError
from vukery.core.machine import Machine
from vukery.core.modes import Mode
from vukery.core.player import Player
from vukery.core.switches import Switch
from vukery.dashboard.state import DashboardState
from vukery.mc.state import MediaState

__all__ = ["GameRig", "expect"]


class GameRig:
    """Runs a game folder in the test environment, for specs."""

    def __init__(self, game_dir: Path | str, simulate_balls: bool = True, fill_troughs: bool = True,
                 dashboard: bool = False):
        """``simulate_balls``: ejected balls leave the trough by themselves (as in development).
        ``fill_troughs``: every trough switch starts active (all balls home).
        ``dashboard``: attach an in-process vuk me dashboard, as ``rig.dashboard``."""
        self.loop = asyncio.new_event_loop()
        self.clock = VirtualClock(self.loop)
        try:
            self.machine = Machine.from_folder(Path(game_dir), env="test", clock=self.clock, dashboard=dashboard)
            self.machine.platform.simulate_balls = simulate_balls
            self.posted: list[tuple[str, dict[str, Any]]] = []
            self.machine.events.monitors.append(lambda event, kwargs: self.posted.append((event, kwargs)))
            # an in-process media controller on virtual time: what the screens would show, entrances included
            self.display = MediaState(now=self.clock.now)
            if self.machine.media is not None:   # listening from power-on, so it hears the first sounds too
                self.machine.media.attach(self.display.apply)
            self.loop.run_until_complete(self.machine.start())
            self.dashboard = DashboardState(now=self.clock.now)  # what vuk me would show
            if self.machine.media is not None:
                self.display.apply(self.machine.media.welcome())   # the scenes the modes defined as it started
                if dashboard:
                    self.machine.media.attach(self.dashboard.apply, dashboard=True)
            if fill_troughs:
                for device in self.machine.ball_devices.values():
                    if "trough" not in device.config.tags:
                        continue   # balls start in the trough, as in the engine
                    for name in device.config.ball_switches:
                        self.machine.set_switch(name, 1)
            self.advance()
        except BaseException:
            self.loop.close()
            raise

    # --- actions

    def switch(self, *names: str, state: str | None = None, hold: float = 0.0, times: int = 1,
               every: float = 0.0) -> None:
        """Change one or more switches, then let the machine react.

        - no ``state``: a tap (active, then inactive), held for ``hold`` seconds;
        - ``state="active"`` or ``"inactive"``: set it and leave it;
        - ``times`` / ``every``: repeat, ``every`` seconds apart.
        Several names change at the same moment.
        """
        for name in names:
            self.machine.switches[name]  # fail early on a typo
        match state:
            case None:
                values: tuple[int, ...] = (1, 0)
            case "active":
                values = (1,)
            case "inactive":
                values = (0,)
            case _:
                raise ValueError(f"state must be 'active' or 'inactive', got {state!r}")
        for repeat in range(times):
            if repeat and every:
                self.advance(every)
            for index, value in enumerate(values):
                if index and hold:
                    self.advance(hold)
                for name in names:
                    self.machine.set_switch(name, value)
                self.advance()

    def advance(self, seconds: float = 0.0) -> None:
        """Move time forward, letting everything that comes due happen."""
        self.clock.advance(seconds)

    def start_game(self, players: int = 1) -> None:
        """Press start (a switch tagged ``start``) once per player and let the first ball start."""
        start = self.machine.switches.tagged("start")
        if not start:
            raise ConfigError("No switch is tagged start")
        for _ in range(players):
            self.switch(start[0].name)
        self.advance(1)

    def drain(self, balls: int = 1) -> None:
        """Put balls back into the trough, as if they drained. A ball still waiting in a
        plunger lane (``mechanical_eject``) is shot first: it can't drain from there."""
        trough = self.machine.trough()
        if trough is None:
            raise ConfigError("There's no trough to drain into")
        waiting = [s for d in self.machine.ball_devices.values() if d.config.mechanical_eject
                   for s in d.config.ball_switches if self.machine.switches[s].state]
        for name in waiting[:balls]:
            self.machine.set_switch(name, 0)
            self.advance()
        empty = [s for s in trough.config.ball_switches if not self.machine.switches[s].state]
        for name in empty[:balls]:
            self.machine.set_switch(name, 1)
            self.advance()
        self.advance(1)

    def post(self, event: str, **kwargs: Any) -> None:
        self.machine.events.post(event, **kwargs)
        self.advance()

    def stop(self) -> None:
        if self.loop.is_closed():
            return
        self.machine.stop("test finished")
        pending = [task for task in asyncio.all_tasks(self.loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        settle(self.loop)
        self.loop.close()

    # --- what to look at

    @property
    def game(self) -> Any:
        return self.machine.game

    @property
    def player(self) -> Player:
        if self.machine.game is None or self.machine.game.player is None:
            raise AssertionError("No game is running")
        return self.machine.game.player

    def mode(self, name: str) -> Mode:
        return self.machine.modes[name]

    def switches(self, name: str) -> Switch:
        return self.machine.switches[name]

    def screen(self, display: str | None = None) -> list[str]:
        """The text on a display right now (the first display by default)."""
        return [text.text for text in self.display.texts(display or self._first_display())]

    def scene(self, display: str | None = None) -> str | None:
        """The name of the scene on a display right now."""
        return self.display.showing.get(display or self._first_display())

    def _first_display(self) -> str:
        if self.machine.media is None:
            raise ConfigError("This game has no displays")
        return self.machine.media.default_display

    def times_posted(self, event: str) -> int:
        return sum(1 for name, _ in self.posted if name == event)

    def sounds(self) -> list[str]:
        """The sounds played so far, in order (a pool's pick, not the pool's name)."""
        return [m["sound"] for m in self.display.played] if self.machine.media is not None else []

    def times_played(self, sound: str) -> int:
        """How many times a sound, or any of a pool's, was played."""
        if self.machine.media is None:
            return 0
        return sum(1 for m in self.display.played if sound in (m["sound"], m["name"]))


class Expectation:
    def __init__(self, value: Any):
        self.value = value

    # --- values (named after MPF's assertions: assertEqual, assertTrue, assertIn…)

    def to_equal(self, expected: Any) -> None:
        assert self.value == expected, f"expected {expected!r}, got {self.value!r}"

    def to_be(self, expected: Any) -> None:
        """The very same object (``is``), not just an equal one."""
        assert self.value is expected, f"expected {expected!r} itself, got {self.value!r}"

    def not_to_equal(self, unexpected: Any) -> None:
        assert self.value != unexpected, f"expected anything but {unexpected!r}"

    def to_be_true(self) -> None:
        assert self.value, f"expected something true, got {self.value!r}"

    def to_be_false(self) -> None:
        assert not self.value, f"expected something false, got {self.value!r}"

    def to_be_none(self) -> None:
        assert self.value is None, f"expected None, got {self.value!r}"

    def not_to_be_none(self) -> None:
        assert self.value is not None, "expected a value, got None"

    def to_contain(self, item: Any) -> None:
        assert item in self.value, f"expected {self.value!r} to contain {item!r}"

    def not_to_contain(self, item: Any) -> None:
        assert item not in self.value, f"expected {self.value!r} not to contain {item!r}"

    def to_be_close_to(self, expected: float, within: float = 1e-6) -> None:
        assert abs(self.value - expected) <= within, f"expected {expected!r} (within {within}), got {self.value!r}"

    def to_be_greater_than(self, other: Any) -> None:
        assert self.value > other, f"expected more than {other!r}, got {self.value!r}"

    def to_be_less_than(self, other: Any) -> None:
        assert self.value < other, f"expected less than {other!r}, got {self.value!r}"

    # --- the machine

    def to_be_running(self) -> None:
        mode = self._mode()
        assert mode.active, f"expected mode {mode.name} to be running, but it's stopped"

    def to_be_stopped(self) -> None:
        mode = self._mode()
        assert not mode.active, f"expected mode {mode.name} to be stopped, but it's running"

    def to_be_active(self) -> None:
        switch = self._switch()
        assert switch.state == 1, f"expected switch {switch.name} to be active"

    def to_be_inactive(self) -> None:
        switch = self._switch()
        assert switch.state == 0, f"expected switch {switch.name} to be inactive"

    def to_have_posted(self, event: str, times: int | None = None) -> None:
        rig = self._rig()
        count = rig.times_posted(event)
        match times:
            case None:
                assert count > 0, f"expected {event!r} to have been posted"
            case int():
                assert count == times, f"expected {event!r} posted {times} time(s), got {count}"

    def not_to_have_posted(self, event: str) -> None:
        count = self._rig().times_posted(event)
        assert count == 0, f"expected {event!r} not to have been posted, but it was ({count} time(s))"

    def to_have_played(self, sound: str, times: int | None = None) -> None:
        """A sound, or a pool (any of its sounds), was played."""
        count = self._rig().times_played(sound)
        if times is None:
            assert count > 0, f"expected {sound!r} to have been played, but it wasn't"
        else:
            assert count == times, f"expected {sound!r} played {times} time(s), got {count}"

    def not_to_have_played(self, sound: str) -> None:
        count = self._rig().times_played(sound)
        assert count == 0, f"expected {sound!r} not to have been played, but it was ({count} time(s))"

    def _mode(self) -> Mode:
        match self.value:
            case Mode() as mode:
                return mode
            case _:
                raise TypeError(f"expected a mode, got {self.value!r}")

    def _switch(self) -> Switch:
        match self.value:
            case Switch() as switch:
                return switch
            case _:
                raise TypeError(f"expected a switch, got {self.value!r}")

    def _rig(self) -> GameRig:
        match self.value:
            case GameRig() as rig:
                return rig
            case _:
                raise TypeError(f"expected the game rig, got {self.value!r}")


def expect(value: Any) -> Expectation:
    """``expect(game.player.score).to_equal(1000)``, ``expect(game.mode("base")).to_be_running()``…"""
    return Expectation(value)
