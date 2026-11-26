"""Where everything goes on the ``vuk me`` dashboard. Pure math, no pyglet.

Window units, with the origin at the bottom left (pyglet's). The panes'
sizes come from an ``Arrangement`` (``config/dashboard.yaml``):

1. ``list``: the game, switches, lights, coils and devices, scrolling;
2. the ``backbox`` over a pane per display;
3. the ``playfield``.

Text has a fixed size; the list scrolls instead of shrinking.
"""

from dataclasses import dataclass
from typing import Any

from vukery.media.arrangement import Arrangement

MARGIN = 8
GRAB = 6          # how close to an edge (in window units) the pointer has to be to drag it
TITLE_BAR = 30    # a pane's title strip
ROW = 24          # one list row
SECTION_TITLE = 36
SECTION_GAP = 12
DEFAULT = Arrangement()


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def inset(self, n: float) -> Rect:
        return Rect(self.x + n, self.y + n, max(self.w - 2 * n, 0), max(self.h - 2 * n, 0))

    def at(self, fx: float, fy: float) -> tuple[float, float]:
        """The point at fractions ``fx``, ``fy`` of the rect, from its bottom left."""
        return self.x + fx * self.w, self.y + fy * self.h

    def fraction(self, px: float, py: float) -> tuple[float, float]:
        """Where a point is in the rect, as fractions from its bottom left, kept inside it."""
        fx = (px - self.x) / self.w if self.w else 0.0
        fy = (py - self.y) / self.h if self.h else 0.0
        return round(min(max(fx, 0.0), 1.0), 3), round(min(max(fy, 0.0), 1.0), 3)


def panes(width: float, height: float, arrangement: Arrangement = DEFAULT) -> dict[str, Rect]:
    """Every pane's rect: ``list``, the middle column's panes, ``playfield``."""
    a = arrangement
    x1, x2 = width * a.x1 / 100, width * a.x2 / 100
    rects = {"list": Rect(0, 0, x1, height)}
    top = height
    for name, percent in a.stack:
        tall = height * percent / 100
        rects[name] = Rect(x1, top - tall, x2 - x1, tall)
        top -= tall
    rects["playfield"] = Rect(x2, 0, width - x2, height)
    return {name: rect.inset(MARGIN / 2) for name, rect in rects.items()}


def content(pane: Rect) -> Rect:
    """A pane without its title strip."""
    return Rect(pane.x + 4, pane.y + 4, pane.w - 8, max(pane.h - TITLE_BAR - 4, 0))


def fit(area: Rect, width: float, height: float) -> Rect:
    """The largest rect of ``width`` × ``height``'s shape that fits in ``area``, centered."""
    scale = min(area.w / width, area.h / height) if width and height else 0
    w, h = width * scale, height * scale
    return Rect(area.x + (area.w - w) / 2, area.y + (area.h - h) / 2, w, h)


@dataclass(frozen=True)
class Edge:
    """A pane edge you can drag: its name in ``Arrangement`` and where to grab it."""

    name: str
    vertical: bool
    grab: Rect


def edges(width: float, height: float, arrangement: Arrangement = DEFAULT) -> list[Edge]:
    """The draggable edges; the middle column's first, since they meet x1 and x2."""
    a, reach = arrangement, GRAB
    x1, x2 = width * a.x1 / 100, width * a.x2 / 100
    result: list[Edge] = []
    top = 0.0
    for i, (_, percent) in enumerate(a.stack[:-1], start=1):
        top += percent
        y = height * (1 - top / 100)
        result.append(Edge(f"y{i}", False, Rect(x1 + reach, y - reach, x2 - x1 - 2 * reach, 2 * reach)))
    result += [Edge("x1", True, Rect(x1 - reach, 0, 2 * reach, height)),
               Edge("x2", True, Rect(x2 - reach, 0, 2 * reach, height))]
    return result


def edge_at(width: float, height: float, arrangement: Arrangement, px: float, py: float) -> Edge | None:
    return next((e for e in edges(width, height, arrangement) if e.grab.contains(px, py)), None)


def edge_percent(edge: Edge, width: float, height: float, px: float, py: float) -> float:
    """Where the pointer puts ``edge``: % from the left, or % from the top."""
    return px / width * 100 if edge.vertical else (height - py) / height * 100


# --- the list pane


@dataclass(frozen=True)
class ListRow:
    """One row of the list: a section title, a switch, light or coil, or a block of text.

    ``top`` is measured down from the top of the list's content, before scrolling.
    """

    kind: str   # "title", "switch", "light", "coil", "game" or "devices"
    name: str
    top: float
    height: float


def game_lines_needed(layout: dict[str, Any]) -> int:
    """Room for the game section: whose turn, each player, a gap, a heading, the modes."""
    return 1 + int(layout.get("max_players", 4)) + 2 + len(layout.get("modes", []))


def device_lines_needed(layout: dict[str, Any]) -> int:
    return max(len(layout.get("ball_devices", [])) + len(layout.get("flippers", []))
               + len(layout.get("autofire_coils", [])), 1)


def list_rows(layout: dict[str, Any], line_height: float = 20) -> tuple[list[ListRow], float]:
    """The list's rows in order, and its total height. Every section's height is fixed."""
    rows: list[ListRow] = []
    top = 0.0

    def add(kind: str, name: str, tall: float, gap: float = 0) -> None:
        nonlocal top
        rows.append(ListRow(kind, name, top, tall))
        top += tall + gap

    add("title", "Game", SECTION_TITLE)
    add("game", "game", game_lines_needed(layout) * line_height, SECTION_GAP)
    for title, kind, key in (("Switches", "switch", "switches"), ("Lights", "light", "lights"),
                             ("Coils", "coil", "coils")):
        add("title", title, SECTION_TITLE)
        for item in layout.get(key, []):
            add(kind, item["name"], ROW)
        top += SECTION_GAP
    add("title", "Devices", SECTION_TITLE)
    add("devices", "devices", device_lines_needed(layout) * line_height, SECTION_GAP)
    return rows, top


def scroll_limit(total: float, visible: float) -> float:
    """How far the list can scroll."""
    return max(total - visible, 0.0)


def thumb(track: Rect, total: float, visible: float, scroll: float) -> Rect:
    """The scrollbar thumb: its size shows how much is visible, its place how far down."""
    if total <= visible:
        return track
    h = max(track.h * visible / total, 24)
    y = track.y + track.h - h - (track.h - h) * scroll / scroll_limit(total, visible)
    return Rect(track.x, y, track.w, h)


def flipper_spots(layout: dict[str, Any]) -> dict[str, tuple[float, float, float]]:
    """Each flipper's pivot (fractions of the playfield) and which way it points (+1 right, -1 left)."""
    result: dict[str, tuple[float, float, float]] = {}
    for i, flipper in enumerate(layout.get("flippers", [])):
        name = flipper["name"]
        left = "left" in name or ("right" not in name and i % 2 == 0)
        result[name] = (0.3 if left else 0.7, 0.16, 1.0 if left else -1.0)
    return result
