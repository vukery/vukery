"""How ``vuk me`` arranges its panes, and the ``config/dashboard.yaml`` file that stores it.

The dashboard has three columns:

1. ``list``: the game, and every switch, light, coil and device, in one
   scrolling pane, full height, up to half the window wide;
2. the ``backbox`` over one pane per display (named after the display),
   stacked top to bottom in config order. This column takes whatever width
   the other two leave;
3. the ``playfield``, full height, as wide as its 1:2 shape needs, but at
   most a third of the window.

``dashboard: panes:`` stores the list's ``width`` and the middle column's
``height``s, as percentages of the window to the nearest 0.1. The heights
add up to 100. The edges you drag are:

- ``x1``: between the list and the middle column;
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
MAX_LIST_PERCENT = 50.0       # the list pane is at most half the window
MAX_PLAYFIELD_PERCENT = 33.0  # the playfield pane is at most a third of the window
TOLERANCE = 0.2  # how far hand-edited percentages may be off and still add up
PLACES = ("backbox", "playfield")  # the panes switches and lights can be placed in


def _tenth(value: float) -> float:
    return round(value + 0.0, 1)


@dataclass(frozen=True)
class Arrangement:
    """The list's width and the middle column's heights, as percentages of the window."""

    x1: float = 40.0
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
        """What ``dashboard.yaml`` stores: the list's width, the middle column's heights."""
        panes = {"list": {"width": _tenth(self.x1)}}
        for name, height in self.stack:
            panes[name] = {"height": _tenth(height)}
        return panes

    @classmethod
    def from_panes(cls, panes: dict[str, Any], displays: Sequence[str] = ()) -> Arrangement:
        """Read ``dashboard: panes:``. Panes left out keep their default size, if the heights still add up.

        The playfield and the middle column size themselves, so their widths
        (and the playfield's entry) are ignored if they're there.
        """
        default = cls.default(displays)
        names = ["backbox", *displays]
        unknown = sorted(set(panes) - {"list", "playfield", *names})
        if unknown:
            raise ConfigError(f"dashboard: panes: no pane named {', '.join(unknown)} "
                              f"({', '.join(['list', *names, 'playfield'])})")

        def number(name: str, key: str, fallback: float) -> float:
            value = mapping(panes.get(name), f"dashboard: panes: {name}").get(key, fallback)
            try:
                return float(value)
            except (TypeError, ValueError) as e:
                raise ConfigError(f"dashboard: panes: {name}: {key} is a percentage, e.g. 40.0") from e

        x1 = number("list", "width", default.x1)
        if not MIN_PERCENT <= x1 <= MAX_LIST_PERCENT:
            raise ConfigError(f"dashboard: panes: list: width is {MIN_PERCENT} to {MAX_LIST_PERCENT}%, got {x1}")
        heights = [number(name, "height", h) for name, (_, h) in zip(names, default.stack, strict=True)]
        if any(h < MIN_PERCENT for h in heights):
            raise ConfigError(f"dashboard: panes: every pane needs at least {MIN_PERCENT}% of the height")
        if abs(sum(heights) - 100) > TOLERANCE * len(heights):
            raise ConfigError(f"dashboard: panes: the heights of {', '.join(names)} add up to "
                              f"{_tenth(sum(heights))}, not 100")
        heights[-1] = _tenth(100 - sum(heights[:-1]))
        return cls(x1=_tenth(x1), stack=tuple(zip(names, heights, strict=True)))

    def edges(self) -> list[str]:
        return ["x1", *(f"y{i}" for i in range(1, len(self.stack)))]

    def drag(self, edge: str, percent: float) -> Arrangement:
        """Move one edge to ``percent`` (from the left, or from the top), within the limits."""
        m = MIN_PERCENT
        match edge:
            case "x1":
                return replace(self, x1=_tenth(min(max(percent, m), MAX_LIST_PERCENT)))
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
             "  # Pane sizes, as a % of the window. The playfield is as wide as its 1:2 shape",
             "  # needs (at most 33%); the backbox and displays take the rest.",
             "  panes:"]
    for name, size in arrangement.to_panes().items():
        lines.append(f"    {name}:")
        lines += [f"      {key}: {value}" for key, value in size.items()]
    for place in PLACES:
        placed = positions.get(place, {}) if positions is not None else mapping(dashboard.get(place))
        if placed:
            lines.append(f"  {place}:  # switches and lights placed in the {place}: [x, y], each 0 to 1")
            lines += [f"    {name}: {_flow([round(float(v), 3) for v in xy])}" for name, xy in placed.items()]
    text = "\n".join(lines) + "\n"
    if data:  # anything else someone put in this file
        text += "\n" + yaml.safe_dump(data, sort_keys=False)
    path.write_text(text)
