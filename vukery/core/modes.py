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

import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from vukery.core.clock import Timer
from vukery.core.events import BLOCK, Block, Handler
from vukery.core.log import Logs
from vukery.core.scoring import Entry, entries, facility, resolve
from vukery.media.scenes import SceneFunction, scene_name

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
    use_wait_queue: ClassVar[bool] = False  # started by a queue event (game_ending…): hold it until the mode stops
    scenes: ClassVar[tuple[SceneFunction, ...]] = ()  # the @scene functions this mode can show
    scoring: ClassVar[dict[str, Entry]] = {}  # what this mode scores (see vukery.core.scoring)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.__dict__.get("name"):
            cls.name = _snake(cls.__name__)

    def __init__(self, machine: Machine):
        self.machine = machine
        self._wait_queue: Any = None
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

    def show_scene(self, scene: Any, display: str | None = None, priority: int = 0) -> None:
        """Show one of the game's scenes (MPF: ``slide_player``): its function, or its name.

        ``display``: which display (MPF: ``target``); the first one by default.
        ``priority``: added to the mode's priority. The scene goes away when the mode stops.
        """
        if self.machine.media is not None:
            self.machine.media.show(self, scene_name(scene), display, priority)

    def scene_functions(self) -> tuple[SceneFunction, ...]:
        """The scenes this mode can show (its ``scenes``; a built-in mode may take them from its look)."""
        return type(self).scenes

    def publish(self, **values: Any) -> None:
        """Make values available to scenes as ``{<mode name>.<key>}``: ``self.publish(initials="AB")``
        in the high_score mode is ``{high_score.initials}``. They stay until published again."""
        if self.machine.media is not None:
            self.machine.media.publish(self, values)

    def play_sound(self, sound: str, *, volume: float | None = None, loops: int | None = None, priority: int = 0,
                   start_at: float = 0.0, delay: float = 0.0, max_queue_time: float | None = None) -> None:
        """Play a sound, or one of a sound pool's (MPF: ``sound_player``).

        ``volume``, ``loops`` and ``max_queue_time`` replace the sound's own (``sounds:``);
        ``priority`` is added to its own. ``start_at``: seconds into the file. ``delay``:
        seconds to wait first. When the mode stops, its sounds stop or finish their loop
        (the sound's ``mode_end_action``).
        """
        if self.machine.media is not None:
            self.machine.media.play_sound(self, sound, volume=volume, loops=loops, priority=priority,
                                          start_at=start_at, delay=delay, max_queue_time=max_queue_time)
        else:
            self.machine.sounds.resolve(sound, random.Random(), {})  # still explain a name that doesn't exist

    def stop_sound(self, sound: str) -> None:
        """Stop a sound (or a pool's) this mode played."""
        if self.machine.media is not None:
            self.machine.media.stop_sound(self, sound)

    def play_show(self, name: str, *, priority: int = 0, speed: float = 1.0, loops: int = -1, start_step: int = 1,
                  show_tokens: dict[str, Any] | None = None, key: str | None = None,
                  events_when_played: tuple[str, ...] = (), events_when_stopped: tuple[str, ...] = (),
                  events_when_looped: tuple[str, ...] = (), events_when_completed: tuple[str, ...] = ()) -> Any:
        """Play a show (MPF: show_player). ``name`` is one of this mode's (``bumper_flash``) or
        another mode's (``flash_score.bumper_flash``). Its priority is added to the mode's; the
        same ``key`` (the show's name by default) replaces what's playing under it. It stops
        when this mode stops. Returns the running show (stop, pause, resume, advance)."""
        return self.machine.shows.play(name, self, priority=priority, speed=speed, loops=loops,
                                       start_step=start_step, show_tokens=show_tokens, key=key,
                                       events_when_played=events_when_played,
                                       events_when_stopped=events_when_stopped,
                                       events_when_looped=events_when_looped,
                                       events_when_completed=events_when_completed)

    def stop_show(self, key: str | None = None) -> None:
        """Stop one of this mode's shows (by key, which is its name unless you gave one), or all."""
        self.machine.shows.stop(self.name, None if key is None else self._show_key(key))

    def _show_key(self, key: str) -> str:
        own = f"{self.name}.{key}"
        return own if own in self.machine.shows.shows else key

    def remove_scene(self, scene: Any) -> None:
        if self.machine.media is not None:
            self.machine.media.remove(self, scene_name(scene))

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
        if self.use_wait_queue and (queue := kwargs.get("queue")) is not None:
            queue.wait()   # MPF's use_wait_queue: what posted it waits for this mode to finish
            self._wait_queue = queue
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
        self.machine.shows.stop(self.name)  # a mode's shows stop with it, giving their lights back
        self.events.post_queue(f"mode_{self.name}_stopping", callback=lambda: self._stopped(kwargs))

    def _stopped(self, kwargs: dict[str, Any]) -> None:
        def finish() -> None:
            self.mode_stop(**kwargs)
            if self._wait_queue is not None:
                self._wait_queue.clear()
                self._wait_queue = None
            if self.machine.media is not None:
                self.machine.media.remove(self)
                self.machine.media.stop_sounds(self)
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
        # as MPF's: a ball's modes stop inside ball_ending, before lower-priority handlers (tilt) wait on it
        machine.events.add_handler("ball_ending", self._ball_ending, priority=0)

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

    def _ball_ending(self, queue: Any, **_: Any) -> None:
        """Stop the modes that end with the ball, and hold ``ball_ending`` until they have (MPF's order)."""
        stopping = [m for m in self.modes.values() if m.active and m.stop_on_ball_end]
        if not stopping:
            return
        queue.wait()
        waiting = {m.name for m in stopping}
        handlers: list[Any] = []

        def stopped(name: str) -> None:
            waiting.discard(name)
            if not waiting:
                self.machine.events.remove_handlers(handlers)
                queue.clear()

        for mode in stopping:
            handlers.append(self.machine.events.add_handler(
                f"mode_{mode.name}_stopped", lambda name=mode.name, **_: stopped(name)))
        for mode in stopping:
            mode.stop()

    def stop_game_modes(self) -> None:
        for mode in self.modes.values():
            if mode.active and mode.game_mode:
                mode.stop()
