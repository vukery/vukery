"""Coils (MPF: ``coils:``), with limits enforced in the engine.

Defaults follow MPF's ``Driver`` device so migrated configs behave the same:
https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/devices/driver.py

vukery checks every pulse power, hold power and pulse time against the
coil's limits before anything reaches the hardware, and raises
``CoilLimitError`` instead of firing.
"""

from dataclasses import dataclass
from typing import Any

from vukery.core.errors import CoilLimitError, ConfigError
from vukery.platforms.interfaces import DriverConfig, HoldSettings, PulseSettings

DEFAULT_PULSE_MS = 10  # MPF's mpf: default_pulse_ms
DEFAULT_TIMED_ENABLE_MS = 0  # MPF's mpf: default_timed_enable_ms


@dataclass(frozen=True)
class CoilConfig:
    """One entry of the ``coils:`` section. Keys match MPF."""

    name: str
    number: str
    default_pulse_ms: int | None = None
    default_pulse_power: float | None = None
    default_hold_power: float | None = None
    default_timed_enable_ms: int | None = None
    default_recycle: bool | None = None
    max_pulse_ms: int | None = None
    max_pulse_power: float = 1.0
    max_hold_power: float | None = None
    allow_enable: bool = False
    pulse_with_timed_enable: bool = False
    platform_settings: dict[str, Any] | None = None

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any]) -> CoilConfig:
        known = set(cls.__dataclass_fields__) - {"name"}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ConfigError(f"coils: {name}: unknown setting(s): {', '.join(unknown)}")
        return cls(name=name, **{key: data[key] for key in data})


def _power(value: float, what: str, coil: str) -> float:
    match value:
        case int() | float() if 0.0 <= value <= 1.0:
            return float(value)
        case _:
            raise CoilLimitError(f"Coil {coil}: {what} must be between 0.0 and 1.0, got {value!r}")


class Coil:
    """A coil. ``pulse``, ``enable`` and ``timed_enable`` check limits before touching hardware."""

    def __init__(self, config: CoilConfig, platform: Any, max_pulse_ms: int):
        self.config = config
        self.name = config.name
        self.platform_max_pulse_ms = max_pulse_ms
        self.hw_driver = platform.configure_driver(self.driver_config(), config.number, config.platform_settings)

    # --- resolved settings (MPF's get_and_verify_* rules, with real range checks)

    def pulse_ms(self, pulse_ms: int | None = None) -> int:
        match pulse_ms, self.config.default_pulse_ms:
            case None, None:
                pulse_ms = DEFAULT_PULSE_MS
            case None, int() as default:
                pulse_ms = default
            case _:
                pass
        limit = self.config.max_pulse_ms or self.platform_max_pulse_ms
        if not 0 <= pulse_ms <= limit:
            raise CoilLimitError(f"Coil {self.name}: pulse of {pulse_ms}ms is outside 0-{limit}ms")
        return pulse_ms

    def pulse_power(self, pulse_power: float | None = None) -> float:
        if pulse_power is None:
            pulse_power = self.config.default_pulse_power if self.config.default_pulse_power is not None else 1.0
        power = _power(pulse_power, "pulse power", self.name)
        if power > self.config.max_pulse_power:
            raise CoilLimitError(f"Coil {self.name}: pulse power {power} is above max_pulse_power "
                                 f"{self.config.max_pulse_power}")
        return power

    def max_hold_power(self) -> float:
        match self.config:
            case CoilConfig(max_hold_power=float() | int() as limit) if limit:
                return float(limit)
            case CoilConfig(allow_enable=True):
                return 1.0
            case CoilConfig(default_hold_power=float() | int() as default) if default:
                return float(default)
            case _:
                return 0.0

    def hold_power(self, hold_power: float | None = None) -> float:
        match hold_power, self.config:
            case None, CoilConfig(default_hold_power=float() | int() as default) if default:
                hold_power = default
            case None, CoilConfig(max_hold_power=float() | int() as limit) if limit:
                hold_power = limit
            case None, CoilConfig(allow_enable=True):
                hold_power = 1.0
            case None, _:
                hold_power = 0.0
            case _:
                pass
        power = _power(hold_power, "hold power", self.name)
        if power > self.max_hold_power():
            raise CoilLimitError(f"Coil {self.name}: hold power {power} is above its limit {self.max_hold_power()}")
        return power

    def timed_enable_ms(self, timed_enable_ms: int | None = None) -> int:
        if timed_enable_ms is None:
            timed_enable_ms = self.config.default_timed_enable_ms or DEFAULT_TIMED_ENABLE_MS
        if timed_enable_ms < 0:
            raise CoilLimitError(f"Coil {self.name}: timed enable of {timed_enable_ms}ms is negative")
        return timed_enable_ms

    def driver_config(self) -> DriverConfig:
        """What the platform needs to configure the hardware driver."""
        return DriverConfig(
            name=self.name,
            default_pulse_ms=self.pulse_ms(),
            default_pulse_power=self.pulse_power(),
            default_hold_power=self.hold_power(),
            default_timed_enable_ms=self.timed_enable_ms(),
            default_recycle=self.config.default_recycle,
            max_pulse_ms=self.config.max_pulse_ms,
            max_pulse_power=self.config.max_pulse_power,
            max_hold_power=self.config.max_hold_power,
        )

    # --- actions

    def pulse(self, pulse_ms: int | None = None, pulse_power: float | None = None) -> None:
        ms, power = self.pulse_ms(pulse_ms), self.pulse_power(pulse_power)
        if self.config.pulse_with_timed_enable:
            self.timed_enable(pulse_ms=ms, pulse_power=power)
            return
        self.hw_driver.pulse(PulseSettings(power=power, duration=ms))

    def enable(self, pulse_ms: int | None = None, pulse_power: float | None = None,
               hold_power: float | None = None) -> None:
        ms, power, hold = self.pulse_ms(pulse_ms), self.pulse_power(pulse_power), self.hold_power(hold_power)
        if hold == 0.0:
            raise CoilLimitError(f"Coil {self.name} can't be enabled: it has no hold power "
                                 "(set default_hold_power, max_hold_power or allow_enable)")
        self.hw_driver.enable(PulseSettings(power=power, duration=ms), HoldSettings(power=hold))

    def timed_enable(self, timed_enable_ms: int | None = None, hold_power: float | None = None,
                     pulse_ms: int | None = None, pulse_power: float | None = None) -> None:
        self.hw_driver.timed_enable(
            PulseSettings(power=self.pulse_power(pulse_power), duration=self.pulse_ms(pulse_ms)),
            HoldSettings(power=self.hold_power(hold_power), duration=self.timed_enable_ms(timed_enable_ms)),
        )

    def disable(self) -> None:
        self.hw_driver.disable()
