"""What a media controller knows, built only from protocol messages.

Rendering code (pyglet) reads ``MediaState``; it never talks to the engine.
That keeps everything here testable without a screen.
"""

import string
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from vukery.core.yaml_values import mapping


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
    """A text widget, resolved and ready to draw."""

    text: str
    x: float
    y: float
    size: float
    color: str
    anchor: str


class MediaState:
    def __init__(self) -> None:
        self.displays: dict[str, dict[str, Any]] = {}
        self.slides: dict[str, dict[str, Any]] = {}
        self.showing: dict[str, str | None] = {}
        self.players: dict[int, dict[str, Any]] = {}
        self.current: int | None = None
        self.connected = False
        self.engine_stopped = False

    def apply(self, message: dict[str, Any]) -> None:
        match message:
            case {"type": "welcome"}:
                self.displays = mapping(message.get("displays"))
                self.slides = mapping(message.get("slides"))
                self.showing = {str(k): v for k, v in mapping(message.get("showing")).items()}
                self.players = {int(k): mapping(v) for k, v in mapping(message.get("players")).items()}
                self.current = message.get("player")
                self.connected = True
            case {"type": "show", "display": str() as display, "slide": slide}:
                self.showing[display] = slide
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

    def background(self, display: str) -> str:
        slide = self.slides.get(self.showing.get(display) or "")
        return str(slide["background"]) if slide else "000000"

    def texts(self, display: str) -> list[DrawText]:
        """The current slide's text widgets on ``display``, with live values filled in."""
        slide = self.slides.get(self.showing.get(display) or "")
        if not slide:
            return []
        player = SimpleNamespace(**self.players.get(self.current or 0, {}), number=self.current or "")
        result: list[DrawText] = []
        for widget in slide.get("widgets", []):
            match widget:
                case {"type": "text", "text": str() as text}:
                    result.append(DrawText(_FORMATTER.format(text, player=player), float(widget["x"]),
                                           float(widget["y"]), float(widget["size"]), str(widget["color"]),
                                           str(widget["anchor"])))
                case _:
                    pass
        return result
