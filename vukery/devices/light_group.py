"""Light groups (``light_groups:``): an ordered set of lights that acts like one light.

```yaml
light_groups:
  hole_score_lanes: l_lane_1, l_lane_2, l_lane_3   # or a list
```

The order means something: it's the columns of a show's ``frames`` grid, and
the order a chase runs in. A group does what a light does (``color``, ``on``,
``off``, ``remove``), to every light in it.
"""

from collections.abc import Iterator, Mapping
from typing import Any

from vukery.core.errors import ConfigError
from vukery.core.yaml_values import names
from vukery.devices.light import Light


class LightGroup:
    def __init__(self, name: str, lights: list[Light]):
        self.name = name
        self.lights = lights

    @classmethod
    def from_yaml(cls, name: str, value: Any, lights: Mapping[str, Light]) -> LightGroup:
        members = names(value, f"light_groups: {name}")
        if not members:
            raise ConfigError(f"light_groups: {name}: list its lights, in order")
        if name in lights:
            raise ConfigError(f"light_groups: {name}: there's already a light with that name")
        if unknown := [member for member in members if member not in lights]:
            raise ConfigError(f"light_groups: {name}: no light named {', '.join(unknown)}")
        return cls(name, [lights[member] for member in members])

    def __iter__(self) -> Iterator[Light]:
        return iter(self.lights)

    def __len__(self) -> int:
        return len(self.lights)

    def __getitem__(self, index: int) -> Light:
        return self.lights[index]

    def __repr__(self) -> str:
        return f"<LightGroup {self.name}: {', '.join(light.name for light in self.lights)}>"

    def color(self, color: Any, fade_ms: int | None = None, priority: int = 0, key: str | None = None) -> None:
        for light in self.lights:
            light.color(color, fade_ms, priority, key)

    def on(self, fade_ms: int | None = None, priority: int = 0, key: str | None = None) -> None:
        for light in self.lights:
            light.on(fade_ms, priority, key)

    def off(self, fade_ms: int | None = None, priority: int = 0, key: str | None = None) -> None:
        for light in self.lights:
            light.off(fade_ms, priority, key)

    def remove(self, key: str | None, fade_ms: int | None = None) -> None:
        for light in self.lights:
            light.remove(key, fade_ms)
