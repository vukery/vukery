"""How ``vuk me`` arranges its panes, and the ``config/dashboard.yaml`` file that stores it.

The dashboard always has the same three columns:

1. switches and lights in the top row, coils and devices in the bottom row;
2. the backbox over the game;
3. the playfield, full height.

``dashboard: panes:`` gives each pane's ``width`` and ``height`` as a
percentage of the window, to the nearest 0.1. They have to fit together:
panes in a row share its height, column 1's two rows are as wide as each
other, and so on. Inside, they come down to six edges, the ones you drag:

- ``x1``: the edge between columns 1 and 2;
- ``x2``: the edge between columns 2 and 3;
- ``s1``, ``s2``: the edges inside column 1's top and bottom rows;
- ``y1``: the edge between column 1's rows (from the top);
- ``y2``: the edge between the backbox and the game (from the top).

``vuk me`` rewrites ``config/dashboard.yaml`` when an edge is dragged, unless
``arrangement_lock: true``.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from vukery.core.errors import ConfigError
from vukery.core.yaml_values import mapping

PANES = ("switches", "lights", "coils", "devices", "backbox", "game", "playfield")
MIN_PERCENT = 5.0
TOLERANCE = 0.2  # how far hand-edited percentages may be off and still fit together


def _tenth(value: float) -> float:
    return round(value + 0.0, 1)


@dataclass(frozen=True)
class Arrangement:
    """The six edges, as percentages of the window (y from the top)."""

    x1: float = 43.8
    x2: float = 71.9
    s1: float = 21.9
    s2: float = 21.9
    y1: float = 50.0
    y2: float = 50.0

    def to_panes(self) -> dict[str, dict[str, float]]:
        """Each pane's width and height, as written to ``dashboard.yaml``."""
        size = {
            "switches": (self.s1, self.y1),
            "lights": (self.x1 - self.s1, self.y1),
            "coils": (self.s2, 100 - self.y1),
            "devices": (self.x1 - self.s2, 100 - self.y1),
            "backbox": (self.x2 - self.x1, self.y2),
            "game": (self.x2 - self.x1, 100 - self.y2),
            "playfield": (100 - self.x2, 100.0),
        }
        return {name: {"width": _tenth(w), "height": _tenth(h)} for name, (w, h) in size.items()}

    @classmethod
    def from_panes(cls, panes: dict[str, Any]) -> Arrangement:
        """Read ``dashboard: panes:``. Panes left out keep their default size, if they still fit."""
        default = cls().to_panes()
        unknown = sorted(set(panes) - set(PANES))
        if unknown:
            raise ConfigError(f"dashboard: panes: no pane named {', '.join(unknown)} ({', '.join(PANES)})")
        size: dict[str, tuple[float, float]] = {}
        for name in PANES:
            entry = mapping(panes.get(name), f"dashboard: panes: {name}") or default[name]
            try:
                size[name] = (float(entry.get("width", default[name]["width"])),
                              float(entry.get("height", default[name]["height"])))
            except (TypeError, ValueError) as e:
                raise ConfigError(f"dashboard: panes: {name}: width and height are percentages, e.g. 21.9") from e
        x1 = size["switches"][0] + size["lights"][0]
        result = cls(x1=_tenth(x1), x2=_tenth(x1 + size["backbox"][0]), s1=size["switches"][0],
                     s2=size["coils"][0], y1=size["switches"][1], y2=size["backbox"][1])
        for name, fitted in result.to_panes().items():
            w, h, given = fitted["width"], fitted["height"], size[name]
            if abs(given[0] - w) > TOLERANCE or abs(given[1] - h) > TOLERANCE:
                raise ConfigError(
                    f"dashboard: panes: {name} is {given[0]} × {given[1]}%, but the other panes leave it "
                    f"{w} × {h}%. Panes in a row share its height, column 1's rows are equally wide, "
                    "and the widths across add up to 100.")
        if any(w < MIN_PERCENT or h < MIN_PERCENT for w, h in size.values()):
            raise ConfigError(f"dashboard: panes: every pane needs at least {MIN_PERCENT}% each way")
        return result

    def drag(self, edge: str, percent: float) -> Arrangement:
        """Move one edge to ``percent``, keeping every pane at least ``MIN_PERCENT`` each way."""
        m = MIN_PERCENT
        match edge:
            case "x1":
                x1 = min(max(percent, 2 * m), self.x2 - m)
                ratio = x1 / self.x1  # the rows' inner edges keep their proportions
                return replace(self, x1=_tenth(x1), s1=_tenth(self.s1 * ratio), s2=_tenth(self.s2 * ratio))
            case "x2":
                return replace(self, x2=_tenth(min(max(percent, self.x1 + m), 100 - m)))
            case "s1":
                return replace(self, s1=_tenth(min(max(percent, m), self.x1 - m)))
            case "s2":
                return replace(self, s2=_tenth(min(max(percent, m), self.x1 - m)))
            case "y1":
                return replace(self, y1=_tenth(min(max(percent, m), 100 - m)))
            case "y2":
                return replace(self, y2=_tenth(min(max(percent, m), 100 - m)))
            case _:
                raise ValueError(f"No edge named {edge!r}")


HEADER = """\
# vuk me's dashboard. vuk me rewrites this file when you drag the edge of a pane,
# unless arrangement_lock is true. Hand edits are fine, too.
"""


def _flow(value: Any) -> str:
    return yaml.safe_dump(value, default_flow_style=True, width=1000).strip()


def write_config(path: Path, arrangement: Arrangement) -> None:
    """Save ``arrangement`` to ``config/dashboard.yaml``, keeping the file's other settings."""
    data = mapping(yaml.safe_load(path.read_text()) if path.is_file() else None, str(path))
    dashboard = mapping(data.pop("dashboard", None), f"{path}: dashboard")
    lines = [HEADER, "dashboard:",
             (f"  arrangement_lock: {'true' if dashboard.get('arrangement_lock') else 'false'}"
              "  # true: the panes can't be resized from vuk me"),
             "  panes:  # each pane's width and height, as a % of the window"]
    for name, size in arrangement.to_panes().items():
        lines.append(f"    {name + ':':<10} {{width: {size['width']}, height: {size['height']}}}")
    playfield = mapping(dashboard.get("playfield"))
    if playfield:
        lines.append("  playfield:  # where switches and lights sit on the virtual playfield: [x, y], each 0 to 1")
        lines += [f"    {name}: {_flow(xy)}" for name, xy in playfield.items()]
    text = "\n".join(lines) + "\n"
    if data:  # anything else someone put in this file
        text += "\n" + yaml.safe_dump(data, sort_keys=False)
    path.write_text(text)
