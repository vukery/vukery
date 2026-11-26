"""What a media controller knows, built only from protocol messages, and what to draw from it.

Rendering code (pyglet) reads ``MediaState``; it never talks to the engine.
``draws(display)`` flattens the scene on a display (and the actors still
exiting the one before it) into rectangles and texts, placed in fractions of
the display, with entrances and exits applied. That keeps all of it testable
without a screen.
"""

import string
import time
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


@dataclass(frozen=True)
class DrawRect:
    """A nested scene's background: its bottom-left corner and size, in fractions of the display."""

    x: float
    y: float
    width: float
    height: float
    color: str


Draw = DrawText | DrawRect


def _ease_out(p: float) -> float:
    return 1 - (1 - p) ** 2


def _ease_in(p: float) -> float:
    return p * p


def _progress(elapsed: float, move: dict[str, Any]) -> float:
    return min(max(elapsed / float(move["seconds"]), 0.0), 1.0)


def longest_exit(data: dict[str, Any]) -> float:
    """How long a scene's exits take: its own, its actors', and those inside nested scenes."""
    own = float(mapping(data.get("exit")).get("seconds", 0.0))
    return max([own, *(longest_exit(actor) for actor in data.get("actors", []))])


class MediaState:
    def __init__(self, now: Callable[[], float] = time.monotonic) -> None:
        self.now = now
        self.displays: dict[str, dict[str, Any]] = {}
        self.scenes: dict[str, dict[str, Any]] = {}
        self.showing: dict[str, str | None] = {}
        self.shown_at: dict[str, float] = {}
        self.leaving: dict[str, tuple[str, float]] = {}   # display -> (scene, when it left)
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
                self.shown_at = {display: float("-inf") for display in self.showing}  # already in place
                self.players = {int(k): mapping(v) for k, v in mapping(message.get("players")).items()}
                self.current = message.get("player")
                self.connected = True
            case {"type": "show", "display": str() as display, "scene": scene}:
                previous = self.showing.get(display)
                if previous and previous != scene and longest_exit(self.scenes.get(previous, {})) > 0:
                    self.leaving[display] = (previous, self.now())
                self.showing[display] = scene
                self.shown_at[display] = self.now()
            case {"type": "player", "number": int() as number, "vars": dict()}:
                self.players.setdefault(number, {}).update(mapping(message["vars"]))
            case {"type": "turn", "number": number}:
                self.current = number
                if number is None:
                    self.players = {}
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
            self._flatten(scene, (0.5, 0.5, 1.0, 1.0), now - self.shown_at.get(display, float("-inf")), None,
                          result, top=True)
        if display in self.leaving:
            name, left_at = self.leaving[display]
            gone = self.scenes.get(name, {})
            if now - left_at >= longest_exit(gone):
                del self.leaving[display]
            else:
                self._flatten(gone, (0.5, 0.5, 1.0, 1.0), float("inf"), now - left_at, result, top=True)
        return result

    def texts(self, display: str) -> list[DrawText]:
        """The texts on ``display`` now (what ``GameRig.screen()`` reads)."""
        return [item for item in self.draws(display) if isinstance(item, DrawText)]

    def _player(self) -> SimpleNamespace:
        return SimpleNamespace(**self.players.get(self.current or 0, {}), number=self.current or "")

    def _flatten(self, scene: dict[str, Any], region: tuple[float, float, float, float], since_shown: float,
                 since_left: float | None, out: list[Draw], top: bool = False) -> None:
        """Place a scene's actors in ``region`` (center x, center y, width, height of the display).

        ``since_left`` is set for a scene that's going away: only actors with an
        exit (or inside one that has) are drawn, moving off.
        """
        cx, cy, width, height = region
        if not top and scene.get("background"):
            out.append(DrawRect(cx - width / 2, cy - height / 2, width, height, str(scene["background"])))
        for actor in scene.get("actors", []):
            x = cx + (float(actor.get("x", 0.5)) - 0.5) * width
            y = cy + (float(actor.get("y", 0.5)) - 0.5) * height
            dx, dy, leaving_still = 0.0, 0.0, since_left
            if since_left is not None:
                if "exit" in actor:
                    p = _progress(since_left, actor["exit"])
                    if p >= 1:
                        continue
                    far = OFFSTAGE[actor["exit"]["side"]]
                    dx, dy = far[0] * _ease_in(p), far[1] * _ease_in(p)
                    leaving_still = None  # everything inside it moves with it
                elif actor.get("type") != "scene":
                    continue
            elif "enter" in actor:
                p = _ease_out(_progress(since_shown, actor["enter"]))
                far = OFFSTAGE[actor["enter"]["side"]]
                dx, dy = far[0] * (1 - p), far[1] * (1 - p)
            match actor.get("type"):
                case "text":
                    text = _FORMATTER.format(str(actor["text"]), player=self._player())
                    out.append(DrawText(text, x + dx, y + dy, float(actor.get("size", 0.1)) * height,
                                        str(actor.get("color", "ffffff")), str(actor.get("anchor", "center"))))
                case "scene":
                    inner = (x + dx, y + dy, float(actor.get("width", 1.0)) * width,
                             float(actor.get("height", 1.0)) * height)
                    self._flatten(actor, inner, since_shown, leaving_still, out)
                case _:
                    pass
