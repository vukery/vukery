"""Scenes and actors: what a display shows, defined in Python and sent to media controllers as data.

A **scene** is a container: a background and the **actors** in it. An actor is
a ``Text``, or another scene placed inside this one (MPF's slides and widgets,
as one idea). Scenes are made by functions in a mode's ``scenes.py``::

    from vukery.media.scenes import Scene, Text, scene

    @scene
    def ball_info():
        return Scene(
            Text("PLAYER {player.number}", y=0.65, size=0.2),
            Text("BALL {player.ball}", y=0.3, size=0.2, color="ffcc00"),
            background="202060",
        )

    @scene
    def score():
        return Scene(
            Text("{player.score:,}", y=0.6, size=0.3).enters("left"),
            ball_info().placed(x=0.75, y=0.15, width=0.4, height=0.25),   # a scene inside a scene
        )

- **Placement:** an actor's ``x`` and ``y`` are where its center goes, as
  fractions of its parent scene (``0.5, 0.5`` is the middle); a text's
  ``size`` is its height, as a fraction of the parent's. A placed scene's
  ``width`` and ``height`` are fractions of its parent too, so everything
  scales with the display.
- **Movement:** ``.enters("left", seconds=0.3)`` slides an actor in from that
  side when the scene appears; ``.exits("right")`` slides it out when the
  scene goes away. Sides: left, right, top, bottom.
- **Live values:** ``{player.score:,}`` is filled in by the media controller,
  with Python formatting, from the current player's variables.
"""

import copy
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Self, cast

from vukery.core.errors import ConfigError

SIDES = ("left", "right", "top", "bottom")


def _color(value: str) -> str:
    text = value.lstrip("#")
    if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
        raise ConfigError(f"Not a color: {value!r} (use 6 hex digits, e.g. 'ffcc00')")
    return text.lower()


def _with[T](actor: T, **changes: Any) -> T:
    """A copy of a (frozen) actor with some fields changed."""
    changed = copy.copy(actor)
    for name, value in changes.items():
        object.__setattr__(changed, name, value)
    return changed


@dataclass(frozen=True)
class Move:
    """How an actor enters or exits: from or to a side, over some seconds."""

    side: str
    seconds: float = 0.3

    def __post_init__(self) -> None:
        if self.side not in SIDES:
            raise ConfigError(f"An actor enters and exits {', '.join(SIDES)}, not {self.side!r}")
        if self.seconds <= 0:
            raise ConfigError(f"An entrance or exit takes some time, not {self.seconds}")


@dataclass(frozen=True)
class Actor:
    """Anything in a scene. Every actor is placed and moves the same way."""

    x: float = 0.5
    y: float = 0.5
    enter: Move | None = field(default=None, kw_only=True)
    exit: Move | None = field(default=None, kw_only=True)

    def enters(self, side: str, seconds: float = 0.3) -> Self:
        """Slide in from ``side`` when the scene appears."""
        return _with(self, enter=Move(side, seconds))

    def exits(self, side: str, seconds: float = 0.3) -> Self:
        """Slide out to ``side`` when the scene goes away."""
        return _with(self, exit=Move(side, seconds))

    def to_data(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class Text(Actor):
    """A line of text. ``size`` is its height, as a fraction of its scene's."""

    text: str = ""
    size: float = 0.1
    color: str = "ffffff"
    anchor: str = "center"  # left, center or right: which part of the text is at x

    def __init__(self, text: str, x: float = 0.5, y: float = 0.5, size: float = 0.1, color: str = "ffffff",
                 anchor: str = "center", *, enter: Move | None = None, exit: Move | None = None):
        if anchor not in ("left", "center", "right"):
            raise ConfigError(f"Text anchor must be left, center or right, got {anchor!r}")
        for name, value in (("text", text), ("x", x), ("y", y), ("size", size), ("color", _color(color)),
                            ("anchor", anchor), ("enter", enter), ("exit", exit)):
            object.__setattr__(self, name, value)

    def to_data(self) -> dict[str, Any]:
        data = {"type": "text", **asdict(self)}
        return {k: v for k, v in data.items() if v is not None}


@dataclass(frozen=True)
class Scene(Actor):
    """A container: a background and its actors, drawn in order. Placed inside another scene,
    ``width`` and ``height`` are fractions of that scene."""

    actors: tuple[Actor, ...] = ()
    background: str | None = None
    width: float = 1.0
    height: float = 1.0

    def __init__(self, *actors: Actor, background: str | None = None):
        for actor in actors:
            if not isinstance(cast(object, actor), Actor):  # a mistake in a scene function
                raise ConfigError(f"A scene holds actors (Text, or another scene), not {actor!r}")
        object.__setattr__(self, "actors", tuple(actors))
        object.__setattr__(self, "background", None if background is None else _color(background))
        for name, value in (("x", 0.5), ("y", 0.5), ("width", 1.0), ("height", 1.0), ("enter", None),
                            ("exit", None)):
            object.__setattr__(self, name, value)

    def placed(self, x: float = 0.5, y: float = 0.5, width: float = 1.0, height: float = 1.0) -> Scene:
        """Put this scene inside another: its center at ``x``, ``y``, this wide and tall (fractions)."""
        if width <= 0 or height <= 0:
            raise ConfigError("A placed scene needs a width and height above 0")
        return _with(self, x=x, y=y, width=width, height=height)

    def to_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": "scene", "x": self.x, "y": self.y, "width": self.width,
                                "height": self.height, "actors": [actor.to_data() for actor in self.actors]}
        for key, value in (("background", self.background), ("enter", self.enter), ("exit", self.exit)):
            if value is not None:
                data[key] = asdict(value) if isinstance(value, Move) else value
        return data


SceneFunction = Callable[[], Scene]


def scene(function: SceneFunction) -> SceneFunction:
    """Mark a function as a scene, named after the function. List it in the mode's ``scenes``."""
    setattr(function, "scene_name", function.__name__)  # noqa: B010
    return function


def scene_name(value: Any) -> str:
    """The name of a scene, given its function or its name."""
    match value:
        case str():
            return value
        case _ if callable(value) and hasattr(value, "scene_name"):
            return str(getattr(value, "scene_name"))  # noqa: B009
        case _:
            raise ConfigError(f"Not a scene: {value!r} (use a function marked @scene, or its name)")


def build(function: SceneFunction) -> Scene:
    """Run a scene function and check that it made a scene."""
    made = cast(object, function())  # a scene function might return anything
    if not isinstance(made, Scene):
        raise ConfigError(f"Scene {scene_name(function)} returned {made!r}, not a Scene")
    return made
