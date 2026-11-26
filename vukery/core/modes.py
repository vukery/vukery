"""Modes: the one base class for anything that hooks into the machine.

A mode declares when it runs and what it reacts to::

    class HoleScore(Mode):
        priority = 200
        start_on = "ball_started"

        @on.switch("s_hole")
        def hole(self):
            self.score(5000)
            return BLOCK          # lower-priority modes don't score this hit

The lifecycle and its events match MPF's:

- start: ``mode_<name>_will_start`` → ``mode_<name>_starting`` (a queue event)
  → active → ``mode_<name>_started`` → ``mode_start()``
- stop: ``mode_<name>_will_stop`` (switch handlers and delays end here) →
  ``mode_<name>_stopping`` (queue) → ``mode_<name>_stopped`` → ``mode_stop()``
  → event handlers removed

A mode's handlers run at the mode's priority plus their own, as in MPF.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from vukery.core.clock import Timer
from vukery.core.events import BLOCK, Block, Handler
from vukery.core.log import Logs
from vukery.core.scoring import Entry, entries, facility, resolve
from vukery.media.slides import Slide

if TYPE_CHECKING:
    from vukery.core.machine import Machine
    from vukery.core.player import Player

__all__ = ["BLOCK", "Block", "Mode", "on"]


@dataclass(frozen=True)
class _Hook:
    kind: str  # "event" or "switch"
    name: str
    priority: int
    state: int = 1
    hold: float = 0.0


class _On:
    """Decorators that attach a mode method to an event or a switch."""

    @staticmethod
    def event(name: str, priority: int = 0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Run the method when ``name`` is posted. It gets the event's arguments."""
        def decorate(method: Callable[..., Any]) -> Callable[..., Any]:
            hooks = getattr(method, "_vukery_hooks", [])
            method._vukery_hooks = [*hooks, _Hook("event", name, priority)]  # type: ignore[attr-defined]
            return method
        return decorate

    @staticmethod
    def switch(name: str, state: str = "active", hold: float = 0.0,
               priority: int = 0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Run the method when switch ``name`` changes to ``state``.

        ``hold``: only after it has stayed that way this many seconds.
        Return ``BLOCK`` to stop lower-priority modes handling the same hit.
        """
        match state:
            case "active":
                value = 1
            case "inactive":
                value = 0
            case _:
                raise ValueError(f"state must be 'active' or 'inactive', got {state!r}")

        def decorate(method: Callable[..., Any]) -> Callable[..., Any]:
            hooks = getattr(method, "_vukery_hooks", [])
            method._vukery_hooks = [*hooks, _Hook("switch", name, priority, value, hold)]  # type: ignore[attr-defined]
            return method
        return decorate


on = _On()


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class Mode(Logs):
    """Base class for modes. Subclass it and set the class attributes."""

    name: ClassVar[str] = ""
    priority: ClassVar[int] = 100
    start_on: ClassVar[str | tuple[str, ...]] = ()
    stop_on: ClassVar[str | tuple[str, ...]] = ()
    game_mode: ClassVar[bool] = True  # stops when the game ends; can only run during a game
    stop_on_ball_end: ClassVar[bool] = True
    slides: ClassVar[dict[str, Slide]] = {}  # slides this mode can show, by name
    scoring: ClassVar[dict[str, Entry]] = {}  # what this mode scores (see vukery.core.scoring)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.__dict__.get("name"):
            cls.name = _snake(cls.__name__)

    def __init__(self, machine: Machine):
        self.machine = machine
        self.active = False
        self.starting = False
        self.stopping = False
        self._event_handlers: list[Handler] = []
        self._switch_handlers: list[Handler] = []
        self._timed: list[Any] = []
        self._delays: dict[str, Timer] = {}
        self.configure_logging(f"modes.{self.name}")

    def __repr__(self) -> str:
        state = "running" if self.active else "stopped"
        return f"<Mode {self.name} ({state}, priority {self.priority})>"

    # --- conveniences for game code

    @property
    def events(self):
        return self.machine.events

    @property
    def player(self) -> Player | None:
        game = self.machine.game
        return game.player if game else None

    def score(self, points: int, source: str | None = None) -> None:
        """Add points to the current player's score, after every running mode's ``adjust_score``.

        ``source``: what scored (a switch or event name), for adjusters that care.
        """
        if self.player is not None:
            self.player.score += self.machine.adjust_score(points, source)

    def adjust_score(self, points: float, source: str | None) -> float:
        """Override to change every score while this mode runs (multipliers, suppression…).

        Called for each score, on each running mode, highest priority first.
        """
        return points

    def post(self, event: str, **kwargs: Any) -> None:
        self.machine.events.post(event, **kwargs)

    def delay(self, name: str, seconds: float, callback: Callable[[], Any]) -> None:
        """Call ``callback`` after ``seconds``, replacing a pending delay with the same name.

        Delays are cancelled when the mode stops.
        """
        self.cancel_delay(name)

        def fire() -> None:
            self._delays.pop(name, None)
            callback()

        self._delays[name] = self.machine.clock.call_later(seconds, fire)

    def cancel_delay(self, name: str) -> None:
        if timer := self._delays.pop(name, None):
            timer.cancel()

    def show_slide(self, name: str, display: str | None = None, priority: int = 0) -> None:
        """Show one of the game's slides (MPF: ``slide_player``).

        ``display``: which display (MPF: ``target``); the first one by default.
        ``priority``: added to the mode's priority. The slide goes away when the mode stops.
        """
        if self.machine.media is not None:
            self.machine.media.show(self, name, display, priority)

    def remove_slide(self, name: str) -> None:
        if self.machine.media is not None:
            self.machine.media.remove(self, name)

    # --- hooks for subclasses

    def mode_start(self, **kwargs: Any) -> None:
        """Called once the mode has started."""

    def mode_stop(self, **kwargs: Any) -> None:
        """Called once the mode has stopped."""

    # --- lifecycle

    def start(self, **kwargs: Any) -> None:
        if self.active or self.starting:
            return
        if self.game_mode and not self.machine.game:
            self.warning_log("Not starting: it's a game mode and no game is running")
            return
        self.starting = True
        self.events.post(f"mode_{self.name}_will_start")
        self.events.post_queue(f"mode_{self.name}_starting", callback=lambda: self._started(kwargs))

    def _started(self, kwargs: dict[str, Any]) -> None:
        if not self.starting:
            return
        self.starting = False
        self.active = True
        self._add_hooks()
        self.info_log("Started (priority %s)", self.priority)
        self.events.post(f"mode_{self.name}_started", callback=lambda: self.mode_start(**kwargs))

    def stop(self, **kwargs: Any) -> None:
        if not (self.active or self.starting) or self.stopping:
            return
        self.starting = False
        self.stopping = True
        self.events.post(f"mode_{self.name}_will_stop")
        self.events.remove_handlers(self._switch_handlers)
        self._switch_handlers = []
        for timed in self._timed:
            self.machine.switches.remove_timed_handler(timed)
        self._timed = []
        for name in list(self._delays):
            self.cancel_delay(name)
        self.events.post_queue(f"mode_{self.name}_stopping", callback=lambda: self._stopped(kwargs))

    def _stopped(self, kwargs: dict[str, Any]) -> None:
        def finish() -> None:
            self.mode_stop(**kwargs)
            if self.machine.media is not None:
                self.machine.media.remove(self)
            self.events.remove_handlers(self._event_handlers)
            self._event_handlers = []
            self.active = False
            self.stopping = False
            self.info_log("Stopped")

        self.events.post(f"mode_{self.name}_stopped", callback=finish)

    def _add_scoring(self) -> None:
        for key, value in type(self).scoring.items():
            if key in self.machine.switches.switches:
                event = f"{key}_active"
            else:
                if key.startswith("s_"):
                    self.warning_log("scoring: %r isn't a switch, so it's treated as an event name", key)
                event = key
            for variable, amount, block in entries(value):
                handler = self._scoring_handler(key, variable, amount, block)
                self._switch_handlers.append(self.events.add_handler(
                    event, handler, priority=self.priority, facility=facility(variable)))

    def _scoring_handler(self, source: str, variable: str, amount: Any, block: Any) -> Callable[..., Any]:
        def handle(**_: Any) -> Block | None:
            player = self.player
            if player is None:
                return None
            points = resolve(amount, self)
            if variable == "score":
                self.score(points, source)
            else:
                setattr(player, variable, player.get(variable, 0) + points)
            return Block(facility(variable)) if resolve(block, self) else None
        return handle

    def _add_hooks(self) -> None:
        self._add_scoring()
        for attribute in dir(type(self)):
            method: Callable[..., Any] | None = getattr(self, attribute, None)
            if method is None or not callable(method):
                continue
            hooks: list[_Hook] = getattr(method, "_vukery_hooks", [])
            for hook in hooks:
                priority = self.priority + hook.priority
                match hook:
                    case _Hook(kind="event", name=event):
                        self._event_handlers.append(
                            self.events.add_handler(event, method, priority=priority, facility="handlers"))
                    case _Hook(kind="switch", name=switch, hold=hold, state=state) if hold > 0:
                        self._timed.append(self.machine.switches.add_timed_handler(switch, method, hold, state))
                    case _Hook(kind="switch", name=switch, state=state):
                        self.machine.switches[switch]  # fail early on a typo
                        suffix = "active" if state else "inactive"
                        self._switch_handlers.append(self.events.add_handler(
                            f"{switch}_{suffix}", method, priority=priority, facility="handlers"))
                    case _:
                        pass


def _start_events(mode: Mode) -> tuple[str, ...]:
    return (mode.start_on,) if isinstance(mode.start_on, str) else tuple(mode.start_on)


def _stop_events(mode: Mode) -> tuple[str, ...]:
    return (mode.stop_on,) if isinstance(mode.stop_on, str) else tuple(mode.stop_on)


class ModeController:
    """Starts and stops modes on their events, at ball end and at game end."""

    def __init__(self, machine: Machine):
        self.machine = machine
        self.modes: dict[str, Mode] = {}

    def add(self, mode: Mode) -> None:
        self.modes[mode.name] = mode
        events = self.machine.events

        def start(**kwargs: Any) -> None:
            mode.start(**kwargs)

        def stop(**kwargs: Any) -> None:
            mode.stop(**kwargs)

        for event in _start_events(mode):
            events.add_handler(event, start, priority=mode.priority + 1)
        for event in _stop_events(mode):
            # stop handlers run before start handlers on the same event (MPF: stop_priority + 1)
            events.add_handler(event, stop, priority=mode.priority + 2)

    def __getitem__(self, name: str) -> Mode:
        return self.modes[name]

    def running(self) -> list[Mode]:
        return sorted((m for m in self.modes.values() if m.active), key=lambda m: m.priority, reverse=True)

    def stop_for_ball_end(self) -> None:
        for mode in self.modes.values():
            if mode.active and mode.stop_on_ball_end:
                mode.stop()

    def stop_game_modes(self) -> None:
        for mode in self.modes.values():
            if mode.active and mode.game_mode:
                mode.stop()
