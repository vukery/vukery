"""What a media controller knows, built only from protocol messages, and what to draw from it.

Rendering code (pyglet) reads ``MediaState``; it never talks to the engine.
``draws(display)`` flattens the scene on a display (and the actors still
exiting the one before it) into rectangles and texts, placed in fractions of
the display, with entrances, exits, moves and blinks applied. That keeps all
of it testable without a screen.
"""

import string
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from vukery.core.yaml_values import mapping

# where an actor comes from or goes to, in display fractions: one display away
OFFSTAGE = {"left": (-1.0, 0.0), "right": (1.0, 0.0), "top": (0.0, 1.0), "bottom": (0.0, -1.0)}


class _Formatter(string.Formatter):
    """Formats ``{player.score}`` text; anything missing shows as empty instead of failing."""

    def get_field(self, field_name: str, args: Any, kwargs: Any) -> Any:
        try:
            return super().get_field(field_name, args, kwargs)
        except (AttributeError, KeyError, IndexError):
            return "", field_name

    def format_field(self, value: Any, format_spec: str) -> str:
        try:
            return super().format_field(value, format_spec)
        except (TypeError, ValueError):
            return str(value)


_FORMATTER = _Formatter()


@dataclass(frozen=True)
class DrawText:
    """A text, resolved and placed: its anchor point and height in fractions of the display."""

    text: str
    x: float
    y: float
    size: float
    color: str
    anchor: str
    opacity: float = 1.0


@dataclass(frozen=True)
class DrawRect:
    """A nested scene's background: its bottom-left corner and size, in fractions of the display."""

    x: float
    y: float
    width: float
    height: float
    color: str
    opacity: float = 1.0


Draw = DrawText | DrawRect


def _ease_out(p: float) -> float:
    return 1 - (1 - p) ** 2


def _ease_in(p: float) -> float:
    return p * p


def _progress(elapsed: float, move: dict[str, Any]) -> float:
    return min(max(elapsed / float(move["seconds"]), 0.0), 1.0)


def _moved(actor: dict[str, Any], t: float) -> tuple[float, float]:
    """Where an actor is ``t`` seconds into its move (from where it's placed)."""
    x0, y0 = float(actor.get("x", 0.5)), float(actor.get("y", 0.5))
    motion = actor.get("motion")
    if not motion or t <= 0:
        return x0, y0
    seconds = float(motion["seconds"])
    legs = t / seconds                      # how many moves' worth of time has passed
    if motion.get("repeat"):
        legs %= 2 if motion.get("back") else 1
    elif legs >= (2 if motion.get("back") else 1):
        legs = 0.0 if motion.get("back") else 1.0
    p = 2 - legs if legs > 1 else legs      # past 1: on the way back
    return x0 + (float(motion["x"]) - x0) * p, y0 + (float(motion["y"]) - y0) * p


def _opacity(actor: dict[str, Any], t: float) -> float:
    """How visible a blinking actor is ``t`` seconds into its blinking: on first, then off."""
    blink = actor.get("blink")
    if not blink or t < 0:
        return 1.0
    every = float(blink["every"])
    if blink.get("times") is not None and t >= 2 * every * int(blink["times"]):
        return 1.0                           # done blinking
    phase = t % (2 * every)
    if blink.get("fade"):                    # out, then back in
        return 1 - phase / every if phase < every else phase / every - 1
    return 1.0 if phase < every else 0.0


def longest_exit(data: dict[str, Any]) -> float:
    """How long a scene's exits take: its own, its actors', and those inside nested scenes."""
    own = float(mapping(data.get("exit")).get("seconds", 0.0))
    return max([own, *(longest_exit(actor) for actor in data.get("actors", []))])


class MediaState:
    def __init__(self, now: Callable[[], float] = time.monotonic, audio: bool = False) -> None:
        self.now = now
        self.audio = audio   # this media controller plays sound: keep its sound messages for the mixer
        self.tracks: dict[str, dict[str, Any]] = {}
        self.sound_files: dict[str, dict[str, Any]] = {}
        self.played: deque[dict[str, Any]] = deque(maxlen=1000)   # the sounds the engine played, latest last
        self.sound_messages: deque[dict[str, Any]] = deque()     # for the mixer, until it takes them
        self.displays: dict[str, dict[str, Any]] = {}
        self.scenes: dict[str, dict[str, Any]] = {}
        self.showing: dict[str, str | None] = {}
        self.shown_at: dict[str, float] = {}
        self.settled: set[str] = set()   # displays whose scene was already up when we connected: no entrances
        self.leaving: dict[str, tuple[str, float, float, bool]] = {}   # display -> (scene, left, shown, settled)
        self.players: dict[int, dict[str, Any]] = {}
        self.current: int | None = None
        self.connected = False
        self.engine_stopped = False

    def apply(self, message: dict[str, Any]) -> None:
        match message:
            case {"type": "welcome"}:
                self.displays = mapping(message.get("displays"))
                self.scenes = mapping(message.get("scenes"))
                self.showing = {str(k): v for k, v in mapping(message.get("showing")).items()}
                self.shown_at = dict.fromkeys(self.showing, self.now())
                self.settled = set(self.showing)  # already in place: no entrances
                self.players = {int(k): mapping(v) for k, v in mapping(message.get("players")).items()}
                self.current = message.get("player")
                self.tracks = mapping(message.get("tracks"))
                self.sound_files = mapping(message.get("sounds"))
                if self.audio:   # start over with what's playing now (connected late, or the engine restarted)
                    self.sound_messages.clear()
                    self.sound_messages.extend(message.get("playing") or [])
                self.connected = True
            case {"type": "show", "display": str() as display, "scene": scene}:
                previous = self.showing.get(display)
                if previous and previous != scene and longest_exit(self.scenes.get(previous, {})) > 0:
                    self.leaving[display] = (previous, self.now(), self.shown_at.get(display, self.now()),
                                             display in self.settled)
                self.showing[display] = scene
                self.shown_at[display] = self.now()
                self.settled.discard(display)
            case {"type": "player", "number": int() as number, "vars": dict()}:
                self.players.setdefault(number, {}).update(mapping(message["vars"]))
            case {"type": "turn", "number": number}:
                self.current = number
                if number is None:
                    self.players = {}
            case {"type": "sound", "action": str() as action}:
                if action == "play":
                    self.played.append(message)
                if self.audio:
                    self.sound_messages.append(message)
            case {"type": "bye"}:
                self.engine_stopped = True
            case _:
                pass  # unknown messages are ignored, so the protocol can grow

    # --- reading

    def background(self, display: str) -> str:
        scene = self.scenes.get(self.showing.get(display) or "")
        return str(scene["background"]) if scene and scene.get("background") else "000000"

    def draws(self, display: str, now: float | None = None) -> list[Draw]:
        """Everything to draw on ``display`` now, in order: the scene, then any actors still exiting."""
        now = self.now() if now is None else now
        result: list[Draw] = []
        scene = self.scenes.get(self.showing.get(display) or "")
        if scene:
            self._flatten(scene, _Clock(now - self.shown_at.get(display, now), None, display not in self.settled),
                          (0.5, 0.5, 1.0, 1.0), 1.0, result, top=True)
        if display in self.leaving:
            name, left_at, shown_at, settled = self.leaving[display]
            gone = self.scenes.get(name, {})
            if now - left_at >= longest_exit(gone):
                del self.leaving[display]
            else:
                self._flatten(gone, _Clock(now - shown_at, now - left_at, not settled), (0.5, 0.5, 1.0, 1.0), 1.0,
                              result, top=True)
        return result

    def texts(self, display: str) -> list[DrawText]:
        """The texts you could see on ``display`` now (what ``GameRig.screen()`` reads)."""
        return [item for item in self.draws(display) if isinstance(item, DrawText) and item.opacity > 0]

    def _players(self) -> dict[int, SimpleNamespace]:
        """Every player's variables, by number: ``{players[2].score}``."""
        return {number: SimpleNamespace(**variables, number=number) for number, variables in self.players.items()}

    def _player(self) -> SimpleNamespace:
        return SimpleNamespace(**self.players.get(self.current or 0, {}), number=self.current or "")

    def _flatten(self, scene: dict[str, Any], clock: _Clock, region: tuple[float, float, float, float],
                 opacity: float, out: list[Draw], top: bool = False) -> None:
        """Place a scene's actors in ``region`` (center x, center y, width, height of the display).

        For a scene that's going away (``clock.since_left`` set), only actors with an
        exit (or inside one that has) are drawn, moving off.
        """
        cx, cy, width, height = region
        if not top and scene.get("background"):
            out.append(DrawRect(cx - width / 2, cy - height / 2, width, height, str(scene["background"]), opacity))
        for actor in scene.get("actors", []):
            entrance = float(actor["enter"]["seconds"]) if "enter" in actor and clock.entering else 0.0
            t = clock.since_shown - entrance     # moves and blinks start once it has entered
            ax, ay = _moved(actor, t)
            seen = opacity * _opacity(actor, t)
            dx, dy, inner_clock = 0.0, 0.0, clock
            if clock.since_left is not None:
                if "exit" in actor:
                    p = _progress(clock.since_left, actor["exit"])
                    if p >= 1:
                        continue
                    far = OFFSTAGE[actor["exit"]["side"]]
                    dx, dy = far[0] * _ease_in(p), far[1] * _ease_in(p)
                    inner_clock = _Clock(clock.since_shown, None, clock.entering)  # everything inside moves with it
                elif actor.get("type") != "scene":
                    continue
            elif entrance:
                p = _ease_out(_progress(clock.since_shown, actor["enter"]))
                far = OFFSTAGE[actor["enter"]["side"]]
                dx, dy = far[0] * (1 - p), far[1] * (1 - p)
            if seen <= 0:
                continue                         # blinked off: nothing inside it shows either
            x = cx + (ax - 0.5) * width + dx
            y = cy + (ay - 0.5) * height + dy
            match actor.get("type"):
                case "text":
                    text = _FORMATTER.format(str(actor["text"]), player=self._player(), players=self._players())
                    out.append(DrawText(text, x, y, float(actor.get("size", 0.1)) * height,
                                        str(actor.get("color", "ffffff")), str(actor.get("anchor", "center")), seen))
                case "scene":
                    inner = (x, y, float(actor.get("width", 1.0)) * width, float(actor.get("height", 1.0)) * height)
                    self._flatten(actor, inner_clock, inner, seen, out)
                case _:
                    pass


@dataclass(frozen=True)
class _Clock:
    """Time for one scene: since it appeared, since it started going away (if it is), and
    whether its actors still make their entrances (not if it was up before we connected)."""

    since_shown: float
    since_left: float | None
    entering: bool
