"""How ``vuk me`` arranges its panes, and the ``config/dashboard.yaml`` file that stores it.

The dashboard has three columns:

1. ``list``: every switch, light, coil and device, and the game, in one
   scrolling pane, full height;
2. the ``backbox`` over one pane per display (named after the display),
   stacked top to bottom in config order;
3. the ``playfield``, full height.

``dashboard: panes:`` gives each pane's ``width`` and ``height`` as a
percentage of the window, to the nearest 0.1. They have to fit together: the
middle column's panes share its width and their heights add up to 100, and
the widths across add up to 100. The edges you drag are:

- ``x1``: between the list and the middle column;
- ``x2``: between the middle column and the playfield;
- ``y1``, ``y2``…: between the middle column's panes, top to bottom.

``dashboard: backbox:`` and ``dashboard: playfield:`` place switches and
lights in those panes, as ``[x, y]`` fractions from the pane's bottom-left
corner, so they move and scale with it.

``vuk me`` rewrites ``config/dashboard.yaml`` when a pane is resized or
something is placed, unless ``arrangement_lock: true``.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from vukery.core.errors import ConfigError
from vukery.core.yaml_values import mapping

MIN_PERCENT = 5.0
TOLERANCE = 0.2  # how far hand-edited percentages may be off and still fit together
PLACES = ("backbox", "playfield")  # the panes switches and lights can be placed in


def _tenth(value: float) -> float:
    return round(value + 0.0, 1)


@dataclass(frozen=True)
class Arrangement:
    """The panes' edges, as percentages of the window."""

    x1: float = 40.0
    x2: float = 75.0
    stack: tuple[tuple[str, float], ...] = (("backbox", 100.0),)  # the middle column, top to bottom: (pane, height)

    @classmethod
    def default(cls, displays: Sequence[str] = ()) -> Arrangement:
        """The backbox over the displays, which share the rest of the column."""
        if not displays:
            return cls()
        each = _tenth(45.0 / len(displays))
        heights = [55.0] + [each] * len(displays)
        heights[-1] = _tenth(100 - sum(heights[:-1]))
        return cls(stack=tuple(zip(["backbox", *displays], heights, strict=True)))

    def to_panes(self) -> dict[str, dict[str, float]]:
        """Each pane's width and height, as written to ``dashboard.yaml``."""
        panes = {"list": {"width": _tenth(self.x1), "height": 100.0}}
        for name, height in self.stack:
            panes[name] = {"width": _tenth(self.x2 - self.x1), "height": _tenth(height)}
        panes["playfield"] = {"width": _tenth(100 - self.x2), "height": 100.0}
        return panes

    @classmethod
    def from_panes(cls, panes: dict[str, Any], displays: Sequence[str] = ()) -> Arrangement:
        """Read ``dashboard: panes:``. Panes left out keep their default size, if they still fit."""
        default = cls.default(displays).to_panes()
        unknown = sorted(set(panes) - set(default))
        if unknown:
            raise ConfigError(f"dashboard: panes: no pane named {', '.join(unknown)} ({', '.join(default)})")
        size: dict[str, tuple[float, float]] = {}
        for name, fallback in default.items():
            entry = mapping(panes.get(name), f"dashboard: panes: {name}") or fallback
            try:
                size[name] = (float(entry.get("width", fallback["width"])),
                              float(entry.get("height", fallback["height"])))
            except (TypeError, ValueError) as e:
                raise ConfigError(f"dashboard: panes: {name}: width and height are percentages, e.g. 40.0") from e
        if any(w < MIN_PERCENT or h < MIN_PERCENT for w, h in size.values()):
            raise ConfigError(f"dashboard: panes: every pane needs at least {MIN_PERCENT}% each way")
        names = ["backbox", *displays]
        stack = [(name, size[name][1]) for name in names]
        last = _tenth(100 - sum(h for _, h in stack[:-1]))
        x1 = size["list"][0]
        result = cls(x1=_tenth(x1), x2=_tenth(x1 + size["backbox"][0]), stack=(*stack[:-1], (names[-1], last)))
        for name, fitted in result.to_panes().items():
            w, h, given = fitted["width"], fitted["height"], size[name]
            if abs(given[0] - w) > TOLERANCE or abs(given[1] - h) > TOLERANCE * len(names):
                raise ConfigError(
                    f"dashboard: panes: {name} is {given[0]} × {given[1]}%, but the other panes leave it "
                    f"{w} × {h}%. The middle column's panes share its width and their heights add up to "
                    "100; the list and playfield are full height; the widths across add up to 100.")
        return result

    def edges(self) -> list[str]:
        return ["x1", "x2", *(f"y{i}" for i in range(1, len(self.stack)))]

    def drag(self, edge: str, percent: float) -> Arrangement:
        """Move one edge to ``percent`` (from the left, or from the top), keeping panes at least ``MIN_PERCENT``."""
        m = MIN_PERCENT
        match edge:
            case "x1":
                return replace(self, x1=_tenth(min(max(percent, m), self.x2 - m)))
            case "x2":
                return replace(self, x2=_tenth(min(max(percent, self.x1 + m), 100 - m)))
            case _ if edge.startswith("y") and edge[1:].isdigit() and 1 <= int(edge[1:]) < len(self.stack):
                i = int(edge[1:])
                above = sum(h for _, h in self.stack[:i - 1])  # where pane i-1 starts, from the top
                below = above + self.stack[i - 1][1] + self.stack[i][1]  # where pane i ends
                cut = _tenth(min(max(percent, above + m), below - m))
                stack = list(self.stack)
                stack[i - 1] = (stack[i - 1][0], _tenth(cut - above))
                stack[i] = (stack[i][0], _tenth(below - cut))
                return replace(self, stack=tuple(stack))
            case _:
                raise ValueError(f"No edge named {edge!r}")


HEADER = """\
# vuk me's dashboard. vuk me rewrites this file when you resize a pane or drag
# a switch or light into place, unless arrangement_lock is true. Hand edits are
# fine, too.
"""


def _flow(value: Any) -> str:
    return yaml.safe_dump(value, default_flow_style=True, width=1000).strip()


def write_config(path: Path, arrangement: Arrangement,
                 positions: Mapping[str, Mapping[str, Sequence[float]]] | None = None) -> None:
    """Save the panes, and ``positions`` if given, to ``config/dashboard.yaml``, keeping its other settings."""
    data = mapping(yaml.safe_load(path.read_text()) if path.is_file() else None, str(path))
    dashboard = mapping(data.pop("dashboard", None), f"{path}: dashboard")
    lines = [HEADER, "dashboard:",
             (f"  arrangement_lock: {'true' if dashboard.get('arrangement_lock') else 'false'}"
              "  # true: vuk me can't change the layout"),
             "  panes:  # each pane's width and height, as a % of the window"]
    panes = arrangement.to_panes()
    width = max(len(name) for name in panes) + 1
    for name, size in panes.items():
        lines.append(f"    {name + ':':<{width}} {{width: {size['width']}, height: {size['height']}}}")
    for place in PLACES:
        placed = positions.get(place, {}) if positions is not None else mapping(dashboard.get(place))
        if placed:
            lines.append(f"  {place}:  # switches and lights placed in the {place}: [x, y], each 0 to 1")
            lines += [f"    {name}: {_flow([round(float(v), 3) for v in xy])}" for name, xy in placed.items()]
    text = "\n".join(lines) + "\n"
    if data:  # anything else someone put in this file
        text += "\n" + yaml.safe_dump(data, sort_keys=False)
    path.write_text(text)
