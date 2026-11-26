"""Slides and widgets, defined in Python and sent to media controllers as data.

A first, minimal set: a slide has a background color and text widgets.
Text can show live values with ``{player.score}``, ``{player.ball}``,
``{player.number}`` or any other player variable, and Python formatting:
``"{player.score:,}"`` → ``12,345``.

Positions and sizes are fractions of the display, so a slide fits any
resolution: ``x=0.5, y=0.5`` is the center.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

from vukery.core.errors import ConfigError


def _color(value: str) -> str:
    text = value.lstrip("#")
    if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
        raise ConfigError(f"Not a color: {value!r} (use 6 hex digits, e.g. 'ffcc00')")
    return text.lower()


@dataclass(frozen=True)
class Text:
    """A line of text."""

    text: str
    x: float = 0.5
    y: float = 0.5
    size: float = 0.1  # height of the text, as a fraction of the display's height
    color: str = "ffffff"
    anchor: str = "center"  # left, center or right

    def __post_init__(self) -> None:
        _color(self.color)
        if self.anchor not in ("left", "center", "right"):
            raise ConfigError(f"Text anchor must be left, center or right, got {self.anchor!r}")

    def to_data(self) -> dict[str, Any]:
        return {"type": "text", **asdict(self)}


@dataclass(frozen=True)
class Slide:
    """What a display shows: a background and widgets, drawn in order."""

    widgets: tuple[Text, ...] = field(default=())
    background: str = "000000"

    def __init__(self, *widgets: Text, background: str = "000000"):
        object.__setattr__(self, "widgets", tuple(widgets))
        object.__setattr__(self, "background", _color(background))

    def to_data(self) -> dict[str, Any]:
        return {"background": self.background, "widgets": [w.to_data() for w in self.widgets]}
