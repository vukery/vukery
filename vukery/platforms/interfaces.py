"""What vukery passes to hardware platforms, and what they need from vukery.

The settings classes keep the names and fields of MPF's platform interface
(``mpf/core/platform.py``) so code ported from MPF platforms reads the same:
https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/core/platform.py

``PlatformHost`` replaces MPF's ``machine`` object: it's the small set of
services a platform is allowed to use.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class SwitchConfig:
    """A switch as the platform needs it."""

    name: str
    invert: bool = False  # NC switch
    debounce: str = "auto"  # "auto", "quick" or "normal"


@dataclass(frozen=True)
class DriverConfig:
    """A coil or other driver as the platform needs it, with limits resolved."""

    name: str
    default_pulse_ms: int = 10
    default_pulse_power: float = 1.0
    default_hold_power: float = 0.0
    default_timed_enable_ms: int = 0
    default_recycle: bool | None = None
    max_pulse_ms: int | None = None
    max_pulse_power: float = 1.0
    max_hold_power: float | None = None


@dataclass(frozen=True)
class PulseSettings:
    power: float
    duration: int  # ms


@dataclass(frozen=True)
class HoldSettings:
    power: float
    duration: int = 0  # ms; 0 means "until disabled"


@dataclass
class SwitchSettings:
    """A switch's part in a hardware rule."""

    hw_switch: Any
    invert: bool
    debounce: bool


@dataclass
class DriverSettings:
    """A driver's part in a hardware rule."""

    hw_driver: Any
    pulse_settings: PulseSettings
    hold_settings: HoldSettings | None
    recycle: bool | int | None


@dataclass(frozen=True)
class RepulseSettings:
    enable_repulse: bool
    debounce_ms: int


class SerialPort(Protocol):
    """A connected serial port: bytes out, bytes in."""

    def write(self, data: bytes) -> None: ...

    async def read(self, n: int) -> bytes: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class SerialPortInfo:
    """A serial device the OS can see (for auto-detection by USB vendor/product ID)."""

    device: str  # e.g. "/dev/ttyUSB1" or "/dev/cu.usbserial-A"
    vid: int | None
    pid: int | None


class Cancellable(Protocol):
    def cancel(self) -> None: ...


class PlatformHost(Protocol):
    """The services vukery gives a hardware platform."""

    production: bool
    is_shutting_down: bool

    async def open_serial(self, port: str, baud: int) -> SerialPort:
        """Open a serial port. Raises ``OSError`` if it can't be opened."""
        ...

    def list_serial_ports(self) -> list[SerialPortInfo]:
        """The serial devices currently attached."""
        ...

    def schedule_interval(self, callback: Callable[[], None], seconds: float) -> Cancellable: ...

    def call_later(self, name: str, ms: int, callback: Callable[[], object]) -> None:
        """Run ``callback`` after ``ms``, replacing any pending call with the same name."""
        ...

    def cancel_call(self, name: str) -> None: ...

    def switch_changed(self, platform: object, number: int, state: int) -> None:
        """A switch changed. ``state`` is logical: 1 is active, NC switches already inverted."""
        ...

    def sync_switch_states(self, platform: object, hw_states: dict[int, int]) -> None:
        """Bring vukery's switch states in line with a full hardware dump (raw states)."""
        ...

    def stop(self, reason: str) -> None:
        """Stop the machine. Used when hardware fails in a way that isn't safe to continue."""
        ...

    def create_task(self, coro: Any) -> asyncio.Task[Any]: ...

    def now(self) -> float:
        """The machine clock in seconds. Light fades are timed against it."""
        ...


class LightPlatformInterface:
    """One channel of a light, as a platform implements it (MPF's interface of the same name)."""

    def __init__(self, number: str):
        self.number = number

    def set_fade(self, start_brightness: float, start_time: float, target_brightness: float,
                 target_time: float) -> None:
        """Fade from start_brightness at start_time to target_brightness at target_time (0.0-1.0)."""
        raise NotImplementedError

    def get_successor_number(self) -> str:
        """The number of the next channel on the hardware, in config format."""
        raise NotImplementedError
