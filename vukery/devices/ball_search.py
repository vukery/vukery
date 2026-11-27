"""Ball search: when the playfield goes quiet with a ball on it, fire the coils that might free it.

As MPF's (``mpf/core/ball_search.py``), configured on the playfield
(``playfields: playfield:``)::

    playfields:
      playfield:
        enable_ball_search: true
        ball_search_timeout: 15s              # quiet this long, with a ball out: search
        ball_search_interval: 250ms           # between coils
        ball_search_wait_after_iteration: 10s # between rounds

- **Armed** while a ball is on the playfield (in play, and not waiting in a
  plunger lane). Every playfield switch (tagged ``playfield_active``, or an
  autofire coil's switch) starts the ``ball_search_timeout`` over, and stops
  a search that's running.
- **Searching** calls each device that takes part, in ``ball_search_order``:
  ball devices pulse their eject coil (in phase 1 only if they're empty;
  never the trough after that) and autofire coils pulse theirs. After a
  device fires, it waits ``ball_search_interval``; after a whole round,
  ``ball_search_wait_after_iteration``. Three phases of rounds
  (``ball_search_phase_1_searches``…).
- **Giving up** posts ``ball_search_failed``, counts the ball as lost, and
  does ``ball_search_failed_action``: ``new_ball`` (the default), ``end_ball``
  or ``end_game``.
- A game's code can take part: ``machine.ball_search.register(order,
  callback, name)``; the callback gets ``(phase, iteration)`` and returns
  whether it fired something.

Events, MPF's: ``ball_search_started``, ``ball_search_phase_<n>``
(``iteration``), ``ball_search_stopped``, ``ball_search_failed``,
``ball_search_prevents_game_start``; ``cancel_ball_search`` gives up now.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vukery.core.errors import ConfigError
from vukery.core.log import Logs
from vukery.core.shows import seconds
from vukery.core.yaml_values import names

if TYPE_CHECKING:
    from vukery.core.machine import Machine

FAILED_ACTIONS = ("new_ball", "end_ball", "end_game")
SETTINGS = {"enable_ball_search", "ball_search_timeout", "ball_search_interval", "ball_search_wait_after_iteration",
            "ball_search_phase_1_searches", "ball_search_phase_2_searches", "ball_search_phase_3_searches",
            "ball_search_failed_action", "ball_search_block_events", "ball_search_unblock_events",
            "ball_search_enable_events", "ball_search_disable_events",
            "tags", "default_source_device"}   # MPF's playfield settings vukery doesn't need


def _ms(value: Any, where: str) -> float:
    """MPF's ms settings: a bare number is milliseconds; ``"15s"`` and ``"250ms"`` say which."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value) / 1000
    return seconds(value, where)


@dataclass(frozen=True)
class PlayfieldConfig:
    """``playfields: playfield:``, MPF's settings and defaults."""

    enable_ball_search: bool = False
    ball_search_timeout: float = 15.0
    ball_search_interval: float = 0.15
    ball_search_wait_after_iteration: float = 5.0
    phase_searches: tuple[int, int, int] = (3, 3, 4)
    ball_search_failed_action: str = "new_ball"
    ball_search_block_events: tuple[str, ...] = ("flipper_cradle",)
    ball_search_unblock_events: tuple[str, ...] = ("flipper_cradle_release",)
    ball_search_enable_events: tuple[str, ...] = ()
    ball_search_disable_events: tuple[str, ...] = ()

    @classmethod
    def from_yaml(cls, section: dict[str, Any]) -> PlayfieldConfig:
        if extra := sorted(set(section) - {"playfield"}):
            raise ConfigError(f"playfields: only one playfield, named playfield, is supported (not {', '.join(extra)})")
        data: dict[str, Any] = section.get("playfield") or {}
        where = "playfields: playfield"
        if unknown := sorted(set(data) - SETTINGS):
            raise ConfigError(f"{where}: not supported: {', '.join(unknown)}")
        action = str(data.get("ball_search_failed_action", "new_ball"))
        if action not in FAILED_ACTIONS:
            raise ConfigError(f"{where}: ball_search_failed_action is {', '.join(FAILED_ACTIONS)}, not {action!r}")
        defaults = cls()
        return cls(
            enable_ball_search=bool(data.get("enable_ball_search", False)),
            ball_search_timeout=_ms(data.get("ball_search_timeout", "15s"), f"{where}: ball_search_timeout"),
            ball_search_interval=_ms(data.get("ball_search_interval", "150ms"), f"{where}: ball_search_interval"),
            ball_search_wait_after_iteration=_ms(data.get("ball_search_wait_after_iteration", "5s"),
                                                 f"{where}: ball_search_wait_after_iteration"),
            phase_searches=(int(data.get("ball_search_phase_1_searches", 3)),
                            int(data.get("ball_search_phase_2_searches", 3)),
                            int(data.get("ball_search_phase_3_searches", 4))),
            ball_search_failed_action=action,
            ball_search_block_events=_events(data, "ball_search_block_events", defaults.ball_search_block_events),
            ball_search_unblock_events=_events(data, "ball_search_unblock_events",
                                               defaults.ball_search_unblock_events),
            ball_search_enable_events=_events(data, "ball_search_enable_events", ()),
            ball_search_disable_events=_events(data, "ball_search_disable_events", ()),
        )


def _events(data: dict[str, Any], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    return names(data[key], f"playfields: playfield: {key}") if key in data else default


def _ignoring_arguments(method: Callable[[], None]) -> Callable[..., None]:
    def handler(**_: Any) -> None:
        method()
    return handler


@dataclass(frozen=True)
class Searcher:
    """One device's part in ball search: called with (phase, iteration), it returns whether it fired."""

    order: int
    callback: Callable[[int, int], bool]
    name: str
    restore: Callable[[], None] | None = None


class BallSearch(Logs):
    def __init__(self, config: PlayfieldConfig, machine: Machine):
        self.config = config
        self.machine = machine
        self.configure_logging("ball_search")
        self.searchers: list[Searcher] = []
        self.enabled = False        # armed: the timer runs
        self.started = False        # searching now
        self.blocked = False
        self.phase = 0
        self.iteration = 0
        self.lost_balls = 0         # given up on: the machine knows that many fewer balls
        self._iterator: Iterator[Searcher] = iter(())
        self._timer: Any = None     # the quiet timer, or the next step of a search
        self._balls_out = 0
        events = machine.events
        events.add_handler("request_to_start_game", self._request_to_start_game, priority=99)
        events.add_handler("ball_drain", self._lost_ball_found, priority=2000)   # before ball saves
        events.add_handler("cancel_ball_search", self.cancel)
        for handled, method in ((config.ball_search_block_events, self.block),
                                (config.ball_search_unblock_events, self.unblock),
                                (config.ball_search_enable_events, self.enable),
                                (config.ball_search_disable_events, self.disable)):
            for event in handled:
                events.add_handler(event, _ignoring_arguments(method))

    def register(self, order: int, callback: Callable[[int, int], bool], name: str,
                 restore: Callable[[], None] | None = None) -> None:
        """Take part in ball search, called in ``order`` (lowest first) with (phase, iteration)."""
        self.searchers.append(Searcher(order, callback, name, restore))
        self.searchers.sort(key=lambda searcher: searcher.order)

    # --- arming

    def enable(self) -> None:
        if self.blocked or not self.config.enable_ball_search or not self.searchers:
            return
        self.enabled = True
        self.reset_timer()

    def disable(self) -> None:
        self.stop()
        self.enabled = False
        self._cancel_timer()

    def block(self) -> None:
        self.disable()
        self.blocked = True

    def unblock(self) -> None:
        self.blocked = False
        if self._balls_out > 0:
            self.enable()

    def balls_on_playfield(self, count: int) -> None:
        """The playfield's ball count changed (the machine keeps it): armed while there's one."""
        was, self._balls_out = self._balls_out, count
        if count <= 0:
            self.disable()
        elif was <= 0:
            self.enable()

    def playfield_active(self) -> None:
        """A playfield switch was hit: the ball's moving."""
        self.reset_timer()

    def reset_timer(self) -> None:
        if self.started:
            self.stop()
        if self.enabled:
            self._cancel_timer()
            self._timer = self.machine.clock.call_later(self.config.ball_search_timeout, self.start)

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    # --- searching

    def start(self) -> None:
        if not self.enabled or self.started or not self.searchers:
            return
        self.started = True
        self.phase = self.iteration = 1
        self._iterator = iter(list(self.searchers))
        self.info_log("Starting ball search")
        self.machine.events.post("ball_search_started")
        self.machine.events.post("ball_search_phase_1", iteration=1)
        self._run()

    def stop(self) -> None:
        if not self.started:
            return
        self.info_log("Stopping ball search")
        self.started = False
        self._cancel_timer()
        for searcher in self.searchers:
            if searcher.restore:
                searcher.restore()
        self.machine.events.post("ball_search_stopped")

    def _run(self) -> None:
        """One step: call devices in turn until one fires, then wait; between rounds, wait longer."""
        self._timer = None
        if not self.config.phase_searches[self.phase - 1]:
            self.phase += 1
            if self.phase > 3:
                self.give_up()
            else:
                self._run()
            return
        wait = self.config.ball_search_interval
        while True:
            searcher = next(self._iterator, None)
            if searcher is None:
                self.iteration += 1
                if self.iteration > self.config.phase_searches[self.phase - 1]:
                    self.phase += 1
                    self.iteration = 1
                    if self.phase > 3:
                        self.give_up()
                        return
                self.machine.events.post(f"ball_search_phase_{self.phase}", iteration=self.iteration)
                self._iterator = iter(list(self.searchers))
                searcher = next(self._iterator)
                wait = self.config.ball_search_wait_after_iteration
            self.debug_log("Ball search: %s (phase %s, iteration %s)", searcher.name, self.phase, self.iteration)
            if searcher.callback(self.phase, self.iteration):
                self._timer = self.machine.clock.call_later(wait, self._run)
                return

    def cancel(self, **_: Any) -> None:
        """Give up now (MPF: ``cancel_ball_search``)."""
        if self.started:
            self.give_up()

    def give_up(self) -> None:
        """The ball's lost: count it, and do ``ball_search_failed_action``."""
        self.info_log("Ball search failed to find the ball. Giving up")
        self.disable()
        self.machine.events.post("ball_search_failed")
        lost, self._balls_out = self._balls_out, 0
        self.lost_balls += lost
        game = self.machine.game
        if game is None:
            return
        match self.config.ball_search_failed_action:
            case "new_ball":
                trough = self.machine.trough()
                if trough is not None and trough.balls >= lost > 0:
                    for _ in range(lost):
                        trough.eject()
                else:
                    self.info_log("No more balls left. Ending the game")
                    game.end_game()
            case "end_game":
                game.end_game()
            case _:
                game.end_ball()

    def _lost_ball_found(self, balls: int = 0, **_: Any) -> dict[str, Any]:
        """A ball we gave up on rolled into the drain: it's found, not a drain of the ball in play."""
        found = min(balls, self.lost_balls)
        if found <= 0:
            return {}
        self.lost_balls -= found
        self.info_log("A lost ball turned up (%s still lost)", self.lost_balls)
        return {"balls": balls - found}

    def _request_to_start_game(self, **_: Any) -> bool:
        if self.started:
            self.machine.events.post("ball_search_prevents_game_start")
            return False
        return True
