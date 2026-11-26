"""Where everything goes on the ``vuk me`` dashboard. Pure math, no pyglet.

Three columns, in window units with the origin at the bottom left (pyglet's):

1. device panes in a 2×2 grid: switches, lights, coils, other devices;
2. the virtual backbox (a square, top half) over the game and mode state;
3. the virtual playfield, as tall as the window and half as wide.
"""

import math
from dataclasses import dataclass
from typing import Any

MARGIN = 8

# Switches drawn only in the switches pane unless dashboard: playfield: places them:
# the cabinet's buttons and the like aren't on the playfield.
CABINET_WORDS = ("start", "flipper", "tilt", "coin", "door", "button", "service", "launch", "plunger")


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


def panes(width: float, height: float) -> dict[str, Rect]:
    """The dashboard's panes for a window of ``width`` × ``height``."""
    side = min(height / 2, width / 3)  # the backbox square's side, and the playfield's width
    first = width - 2 * side
    half_w, half_h = first / 2, height / 2
    return {
        "switches": Rect(0, half_h, half_w, half_h).inset(MARGIN / 2),
        "lights": Rect(half_w, half_h, half_w, half_h).inset(MARGIN / 2),
        "coils": Rect(0, 0, half_w, half_h).inset(MARGIN / 2),
        "devices": Rect(half_w, 0, half_w, half_h).inset(MARGIN / 2),
        "backbox": Rect(first, height - side, side, side).inset(MARGIN / 2),
        "game": Rect(first, 0, side, height - side).inset(MARGIN / 2),
        "playfield": Rect(width - side, 0, side, height).inset(MARGIN / 2),
    }


def cells(pane: Rect, count: int, header: float = 30, row: float = 26, min_width: float = 170) -> list[Rect]:
    """Rects for ``count`` list items in ``pane``, top to bottom then in more columns.

    Rows shrink (down to 12 units) when there are too many items to fit.
    """
    if count == 0:
        return []
    area = Rect(pane.x + MARGIN, pane.y + MARGIN, pane.w - 2 * MARGIN, pane.h - header - MARGIN)
    max_columns = max(int(area.w // min_width), 1)
    while True:
        rows = max(int(area.h // row), 1)
        columns = math.ceil(count / rows)
        if columns <= max_columns or row <= 12:
            break
        row -= 1
    width = area.w / max(columns, 1)
    top = area.y + area.h
    return [Rect(area.x + (i // rows) * width, top - (i % rows + 1) * row, width, row) for i in range(count)]


def displays(box: Rect, sizes: list[tuple[str, int, int]]) -> dict[str, Rect]:
    """Fit the game's displays in the backbox, stacked top to bottom in config order."""
    if not sizes:
        return {}
    gap = MARGIN * 2
    area = box.inset(gap)
    total_h = sum(h for _, _, h in sizes)
    widest = max(w for _, w, _ in sizes)
    scale = min(area.w / widest, (area.h - gap * (len(sizes) - 1)) / total_h)
    used = total_h * scale + gap * (len(sizes) - 1)
    y = area.y + (area.h + used) / 2
    result: dict[str, Rect] = {}
    for name, w, h in sizes:
        y -= h * scale
        result[name] = Rect(area.x + (area.w - w * scale) / 2, y, w * scale, h * scale)
        y -= gap
    return result


def _side(name: str) -> float | None:
    match name:
        case n if "left" in n:
            return 0.25
        case n if "right" in n:
            return 0.75
        case _:
            return None


def playfield_spots(layout: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Where each switch and light goes on the playfield, as fractions from its bottom left.

    ``dashboard: playfield:`` positions come first. Then:
    - ball device switches sit in a row at the bottom;
    - autofire switches (slingshots, pops) sit by their side;
    - cabinet switches (start, flipper buttons…) stay off the playfield;
    - everything else goes in a grid up top, switches then lights.
    """
    placed: dict[str, tuple[float, float]] = {name: (float(x), float(y)) for name, (x, y) in
                                              layout.get("playfield", {}).items()}
    for device in layout.get("ball_devices", []):
        todo = [s for s in device["switches"] if s not in placed]
        for i, name in enumerate(todo):
            placed[name] = (0.5 + (i - (len(todo) - 1) / 2) * 0.1, 0.03)
    autofire = [a["switch"] for a in layout.get("autofire_coils", []) if a["switch"] not in placed]
    for i, name in enumerate(autofire):
        side = _side(name)
        placed[name] = (side, 0.28) if side is not None else (0.5, 0.75 - i * 0.05)
    rest = [s["name"] for s in layout.get("switches", [])
            if s["name"] not in placed and not any(word in s["name"] or word in s["tags"] for word in CABINET_WORDS)]
    rest += [light["name"] for light in layout.get("lights", []) if light["name"] not in placed]
    columns = 4
    for i, name in enumerate(rest):
        placed[name] = (0.2 + (i % columns) * 0.2, 0.88 - (i // columns) * 0.08)
    return placed


def flipper_spots(layout: dict[str, Any]) -> dict[str, tuple[float, float, float]]:
    """Each flipper's pivot (fractions of the playfield) and which way it points (+1 right, -1 left)."""
    result: dict[str, tuple[float, float, float]] = {}
    for i, flipper in enumerate(layout.get("flippers", [])):
        side = _side(flipper["name"]) or (0.25 if i % 2 == 0 else 0.75)
        result[flipper["name"]] = (0.3 if side < 0.5 else 0.7, 0.16, 1.0 if side < 0.5 else -1.0)
    return result
