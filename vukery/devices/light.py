"""Lights (MPF: ``lights:``): channel mapping, colors and fades.

Channel mapping follows MPF's ``Light`` device so migrated configs map to the
same hardware channels:
https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/devices/light.py

Each light keeps a **stack** of colors, as in MPF: every ``color()`` call has
a priority and a key. The highest priority shows (the latest, on a tie).
Setting a key that's there replaces it; removing a key reveals what's below,
which is how a show gives the light back when it stops. A plain
``light.color("ff0000")`` is priority 0 with no key.

Not here yet: color correction and gamma.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import count
from typing import Any, cast

from vukery.core.errors import ConfigError
from vukery.devices.color_names import NAMED_RGB_COLORS

COLOR_NAMES = {"r": "red", "g": "green", "b": "blue", "w": "white"}

Color = tuple[int, int, int]


def parse_color(value: Any) -> Color:
    """A color from config or code: ``"ff8800"``, ``(255, 136, 0)``, ``[255, 136, 0]``, or one of MPF's
    color names (the web's: ``orange``, ``red``, ``off``…)."""
    match value:
        case str() as text if text.lower() in NAMED_RGB_COLORS:
            red, green, blue = NAMED_RGB_COLORS[text.lower()]
            return red, green, blue
        case str() as text if len(text) == 6:
            try:
                return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
            except ValueError:
                raise ConfigError(f"Not a color: {value!r}") from None
        case (int() as red, int() as green, int() as blue) | [int() as red, int() as green, int() as blue]:
            if not all(0 <= c <= 255 for c in (red, green, blue)):
                raise ConfigError(f"Color components must be 0-255: {value!r}")
            return red, green, blue
        case _:
            raise ConfigError(f"Not a color: {value!r}")


@dataclass(frozen=True)
class LightConfig:
    """One entry of the ``lights:`` section. Keys match MPF."""

    name: str
    number: str | None = None
    type: str | None = None  # channel order, e.g. "rgb", "grb", "rgbw"
    subtype: str | None = None
    previous: str | None = None
    start_channel: str | None = None
    channels: dict[str, Any] | None = None
    platform_settings: dict[str, Any] | None = None
    default_on_color: str = "ffffff"
    fade_ms: int | None = None

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any]) -> LightConfig:
        known = set(cls.__dataclass_fields__) - {"name"}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ConfigError(f"lights: {name}: unknown setting(s): {', '.join(unknown)}")
        values: dict[str, Any] = {key: (str(value) if key in ("number", "start_channel") else value)
                                  for key, value in data.items()}
        return cls(name=name, **values)


@dataclass(frozen=True)
class StackEntry:
    """One color on a light's stack (MPF: LightStackEntry)."""

    priority: int
    key: str | None
    color: Color
    order: int  # breaks ties: the latest wins


class Light:
    """A light made of one or more hardware channels."""

    def __init__(self, config: LightConfig, platform: Any, lights: Mapping[str, Light],
                 now: Callable[[], float]):
        self.config = config
        self.name = config.name
        self.platform = platform
        self.now = now
        self.hw_drivers: dict[str, list[Any]] = {}
        # (start color, start time, target color, target time); target time < 0 means "no fade"
        self._fade: tuple[Color, float, Color, float] = ((0, 0, 0), 0.0, (0, 0, 0), -1.0)
        self.stack: list[StackEntry] = []   # highest priority first; the first one shows
        self._order = count()
        self._load_channels(lights)

    # --- channel mapping (MPF's _load_hw_drivers / _load_hw_driver_sequentially)

    def _load_channels(self, lights: Mapping[str, Light]) -> None:
        match self.config:
            case LightConfig(previous=str() as previous):
                if previous == self.name:
                    raise ConfigError(f"Light {self.name}: 'previous' can't refer to itself")
                if previous not in lights:
                    raise ConfigError(f"Light {self.name}: previous light {previous!r} must be defined first")
                self._load_sequentially(lights[previous].successor_number())
            case LightConfig(start_channel=str() as start):
                self._load_sequentially(start)
            case LightConfig(channels=dict() as channels):
                if self.config.number:
                    raise ConfigError(f"Light {self.name} can't have both number and channels")
                for color, entries in channels.items():
                    listed: list[Any] = cast(list[Any], entries) if isinstance(entries, list) else [entries]
                    for entry in listed:
                        self._add(color, str(entry["number"]))
            case LightConfig(number=str() as number):
                channel_list = [c["number"] for c in
                                self.platform.parse_light_number_to_channels(number, self.config.subtype)]
                for color, channel in zip(self._color_order(len(channel_list)), channel_list, strict=True):
                    self._add(color, channel)
            case _:
                raise ConfigError(f"Light {self.name} needs a number, channels, start_channel or previous")

    def _color_order(self, channel_count: int) -> list[str]:
        match self.config.type, channel_count:
            case str() as order, count if len(order) == count:
                pass
            case str() as order, count:
                raise ConfigError(f"Light {self.name}: type {order!r} doesn't match its {count} channels")
            case None, 1:
                order = "w"
            case None, 3:
                order = "rgb"
            case None, count:
                raise ConfigError(f"Light {self.name}: give it a type; there's no default for {count} channels")
        return [self._color_name(letter) for letter in order]

    def _color_name(self, letter: str) -> str:
        try:
            return COLOR_NAMES[letter]
        except KeyError:
            raise ConfigError(f"Light {self.name}: invalid letter {letter!r} in type {self.config.type!r}") from None

    def _load_sequentially(self, next_channel: str) -> None:
        if self.config.number or self.config.channels:
            raise ConfigError(f"Light {self.name}: can't use start_channel/previous with number or channels")
        if not self.config.type:
            raise ConfigError(f"Light {self.name}: start_channel and previous need a type, e.g. type: rgb")
        for letter in self.config.type:
            driver = self._add(self._color_name(letter), next_channel)
            next_channel = driver.get_successor_number()

    def _add(self, color: str, number: str) -> Any:
        driver = self.platform.configure_light(number, self.config.subtype, self.config,
                                               self.config.platform_settings)
        self.hw_drivers.setdefault(color, []).append(driver)
        return driver

    def successor_number(self) -> str:
        """The channel after this light's last one (for the next light's ``previous:``)."""
        last = max(driver for drivers in self.hw_drivers.values() for driver in drivers)
        return last.get_successor_number()

    # --- color

    def on(self, fade_ms: int | None = None, priority: int = 0, key: str | None = None) -> None:
        self.color(self.config.default_on_color, fade_ms, priority, key)

    def off(self, fade_ms: int | None = None, priority: int = 0, key: str | None = None) -> None:
        self.color((0, 0, 0), fade_ms, priority, key)

    def color(self, color: Any, fade_ms: int | None = None, priority: int = 0, key: str | None = None) -> None:
        """Put a color on the stack. It shows if nothing higher is there."""
        target = parse_color(color)
        fade_ms = self.config.fade_ms or 0 if fade_ms is None else fade_ms
        now = self.now()
        entry = StackEntry(priority, key, target, next(self._order))
        self.stack = [e for e in self.stack if e.key != key]
        self.stack.append(entry)
        self.stack.sort(key=lambda e: (e.priority, e.order), reverse=True)
        if self.stack[0] is entry:
            self._fade_to(target, now, fade_ms)

    def remove(self, key: str | None, fade_ms: int | None = None) -> None:
        """Take ``key``'s color off the stack, showing what's under it (MPF: remove_from_stack_by_key)."""
        if not any(e.key == key for e in self.stack):
            return
        was_top = self.stack[0].key == key
        self.stack = [e for e in self.stack if e.key != key]
        if was_top:
            fade_ms = self.config.fade_ms or 0 if fade_ms is None else fade_ms
            self._fade_to(self.stack[0].color if self.stack else (0, 0, 0), self.now(), fade_ms)

    def _fade_to(self, target: Color, now: float, fade_ms: int) -> None:
        start = self.current_color(now)
        target_time = now + fade_ms / 1000 if fade_ms > 0 else -1.0
        self._fade = (start, now, target, target_time)
        self._send(start, now, target, target_time)

    def current_color(self, now: float | None = None) -> Color:
        start, start_time, target, target_time = self._fade
        now = self.now() if now is None else now
        if target_time < 0 or now >= target_time:
            return target
        ratio = (now - start_time) / (target_time - start_time)
        return tuple(round(s + (t - s) * ratio) for s, t in zip(start, target, strict=True))  # type: ignore[return-value]

    def _send(self, start: Color, start_time: float, target: Color, target_time: float) -> None:
        rgbw = {"red", "green", "blue", "white"} == set(self.hw_drivers)
        for color, drivers in self.hw_drivers.items():
            start_brightness = self._brightness(color, start, rgbw)
            target_brightness = self._brightness(color, target, rgbw)
            for driver in drivers:
                driver.set_fade(start_brightness, start_time, target_brightness, target_time)

    @staticmethod
    def _brightness(channel: str, color: Color, rgbw: bool) -> float:
        """One channel's brightness. RGBW lights use MPF's default ``duck_rgb``:
        white gets the minimum of R, G and B, and the color channels get the rest."""
        red, green, blue = color
        white = min(color) if rgbw else 0
        match channel:
            case "red":
                return (red - white) / 255
            case "green":
                return (green - white) / 255
            case "blue":
                return (blue - white) / 255
            case "white":
                return min(color) / 255
            case _:
                raise ConfigError(f"Invalid light channel {channel!r}")
