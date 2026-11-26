"""Typed config for the FAST platform: the ``fast:`` section of machine YAML.

Keys and defaults match MPF's ``fast:`` config section, so existing MPF
configs load unchanged:
https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/config_spec.yaml
"""

import re
from dataclasses import dataclass, field
from typing import Any

from vukery.core.errors import ConfigError

CONTROLLERS = ("nano", "neuron")


def ms(value: Any) -> int:
    """Parse a time to milliseconds: ``250``, ``"250ms"``, ``"1s"``, ``"1.5s"``."""
    if isinstance(value, bool):
        raise ConfigError(f"Not a time: {value!r}")
    if isinstance(value, int | float):
        return int(value)
    match = re.fullmatch(r"\s*([0-9.]+)\s*(ms|s)?\s*", str(value))
    if not match:
        raise ConfigError(f"Not a time: {value!r}")
    number, unit = float(match.group(1)), match.group(2) or "ms"
    return int(number * 1000) if unit == "s" else int(number)


def ports(value: Any) -> list[str]:
    if value is None:
        return ["auto"]
    return [str(p) for p in value] if isinstance(value, list) else [str(value)]


@dataclass(frozen=True)
class IoBoardConfig:
    name: str
    model: str
    order: int


@dataclass(frozen=True)
class NetConfig:
    controller: str
    port: list[str] = field(default_factory=lambda: ["auto"])
    io_loop: dict[str, IoBoardConfig] = field(default_factory=dict[str, IoBoardConfig])
    baud: int = 921600
    debug: bool = False
    watchdog: int = 1000  # ms
    default_quick_debounce_open: int = 2
    default_quick_debounce_close: int = 2
    default_normal_debounce_open: int = 4
    default_normal_debounce_close: int = 4
    mute_unconfigured_switches: bool = False

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> NetConfig:
        controller = str(data.get("controller", ""))
        if controller not in CONTROLLERS:
            raise ConfigError(
                f"fast: net: controller must be one of {', '.join(CONTROLLERS)}, got {controller!r}"
            )
        io_loop = {
            str(name): IoBoardConfig(name=str(name), model=str(board["model"]), order=int(board["order"]))
            for name, board in (data.get("io_loop") or {}).items()
        }
        orders = sorted(board.order for board in io_loop.values())
        if orders != list(range(1, len(orders) + 1)):
            raise ConfigError("fast: net: io_loop order values must be sequential, starting at 1")
        return cls(
            controller=controller,
            port=ports(data.get("port")),
            io_loop=io_loop,
            baud=int(data.get("baud", 921600)),
            debug=bool(data.get("debug", False)),
            watchdog=ms(data.get("watchdog", 1000)),
            default_quick_debounce_open=ms(data.get("default_quick_debounce_open", 2)),
            default_quick_debounce_close=ms(data.get("default_quick_debounce_close", 2)),
            default_normal_debounce_open=ms(data.get("default_normal_debounce_open", 4)),
            default_normal_debounce_close=ms(data.get("default_normal_debounce_close", 4)),
            mute_unconfigured_switches=bool(data.get("mute_unconfigured_switches", False)),
        )

    def board_names_in_order(self) -> list[str]:
        return [b.name for b in sorted(self.io_loop.values(), key=lambda b: b.order)]


@dataclass(frozen=True)
class RgbConfig:
    port: list[str] = field(default_factory=lambda: ["auto"])
    baud: int = 921600
    debug: bool = False

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> RgbConfig:
        return cls(
            port=ports(data.get("port")),
            baud=int(data.get("baud", 921600)),
            debug=bool(data.get("debug", False)),
        )


@dataclass(frozen=True)
class FastConfig:
    net: NetConfig | None = None
    rgb: RgbConfig | None = None
    debug: bool = False

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> FastConfig:
        unsupported = sorted(set(data) & {"aud", "dmd", "seg", "emu", "exp_int"})
        if unsupported:
            raise ConfigError(f"fast: these FAST ports aren't supported by vukery yet: {', '.join(unsupported)}")
        return cls(
            net=NetConfig.from_yaml(data["net"]) if data.get("net") else None,
            rgb=RgbConfig.from_yaml(data["rgb"]) if data.get("rgb") else None,
            debug=bool(data.get("debug", False)),
        )
