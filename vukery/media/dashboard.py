"""What the engine tells the ``vuk me`` dashboard: the machine's layout once, then its state.

The dashboard is a media controller with ``"dashboard": true`` in its hello.
Besides slides and player variables, it gets:

- ``layout(machine)`` in its welcome: every switch, light, coil, ball device,
  flipper and autofire coil; where to draw them on the virtual playfield;
  and the panes' sizes. All of that is the ``dashboard:`` section,
  usually in ``config/dashboard.yaml``, which the dashboard rewrites when
  you resize a pane;
- ``snapshot(machine)`` in ``state`` messages whenever something changes.

The only thing a dashboard can send back is a switch change, and only on the
simulated platforms. There's no message for coils, so it can never fire one.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from vukery.core.errors import ConfigError
from vukery.core.yaml_values import mapping
from vukery.media.arrangement import Arrangement

if TYPE_CHECKING:
    from vukery.core.machine import Machine


@dataclass(frozen=True)
class DashboardConfig:
    """The ``dashboard:`` section.

    - ``panes:``: each pane's size (see ``vukery.media.arrangement``);
    - ``arrangement_lock:``: true stops vuk me from resizing panes;
    - ``playfield:``: a switch or light name to ``[x, y]``, as fractions of
      the playfield from its bottom-left corner. Anything not listed is
      placed automatically.
    """

    playfield: dict[str, tuple[float, float]]
    arrangement: Arrangement = field(default_factory=Arrangement)
    arrangement_lock: bool = False

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> DashboardConfig:
        unknown = sorted(set(data) - {"playfield", "panes", "arrangement_lock"})
        if unknown:
            raise ConfigError(f"dashboard: not supported: {', '.join(unknown)}")
        positions: dict[str, tuple[float, float]] = {}
        for name, value in mapping(data.get("playfield")).items():
            match value:
                case [int() | float() as x, int() | float() as y] if 0 <= x <= 1 and 0 <= y <= 1:
                    positions[str(name)] = (float(x), float(y))
                case _:
                    raise ConfigError(f"dashboard: playfield: {name}: use [x, y], each from 0 to 1, got {value!r}")
        lock = data.get("arrangement_lock", False)
        if not isinstance(lock, bool):
            raise ConfigError(f"dashboard: arrangement_lock: use true or false, got {lock!r}")
        return cls(positions, Arrangement.from_panes(mapping(data.get("panes"), "dashboard: panes")), lock)


def config(machine: Machine) -> DashboardConfig:
    """The machine's ``dashboard:`` config, checked against its switches and lights."""
    result = DashboardConfig.from_yaml(machine.config.section("dashboard"))
    known = set(machine.switches.switches) | set(machine.lights)
    if unknown := sorted(set(result.playfield) - known):
        raise ConfigError(f"dashboard: playfield: no switch or light named {', '.join(unknown)}")
    return result


def layout(machine: Machine) -> dict[str, Any]:
    """Everything that doesn't change while the machine runs."""
    switch_input = machine.platform_is_simulated()
    settings = config(machine)
    return {
        "switches": [{"name": s.name, "number": s.config.number, "tags": list(s.config.tags)}
                     for s in machine.switches.switches.values()],
        "lights": [{"name": name} for name in machine.lights],
        "coils": [{"name": name} for name in machine.coils],
        "ball_devices": [{"name": name, "switches": list(d.config.ball_switches)}
                         for name, d in machine.ball_devices.items()],
        "flippers": [{"name": name, "coil": f.coil.name, "switch": f.switch.name}
                     for name, f in machine.flippers.items()],
        "autofire_coils": [{"name": name, "coil": a.coil.name, "switch": a.switch.name}
                           for name, a in machine.autofire_coils.items()],
        "playfield": {name: list(xy) for name, xy in settings.playfield.items()},
        "panes": settings.arrangement.to_panes(),
        "arrangement_lock": settings.arrangement_lock,
        "config_file": str(machine.config.game_dir / "config" / "dashboard.yaml"),  # where vuk me saves pane sizes
        "switch_input": switch_input,
    }


def _hex(color: tuple[int, ...]) -> str:
    return "".join(f"{max(0, min(255, int(c))):02x}" for c in color[:3])


def snapshot(machine: Machine) -> dict[str, Any]:
    """The machine's state right now. The server sends it when it differs from the last one."""
    rules = [*machine.flippers.values(), *machine.autofire_coils.values()]
    driven = {r.coil.name for r in rules if r.enabled and r.switch.state}  # fired by a hardware rule
    return {
        "switches": {name: s.state for name, s in machine.switches.switches.items()},
        "lights": {name: _hex(light.current_color()) for name, light in machine.lights.items()},
        "coils": {name: {"pulses": c.pulses, "on": c.enabled or name in driven} for name, c in machine.coils.items()},
        "rules": {r.name: r.enabled for r in rules},
        "ball_devices": {name: [d.balls, d.capacity] for name, d in machine.ball_devices.items()},
        "modes": [[m.name, m.priority] for m in machine.modes.running()],
    }
