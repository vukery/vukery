"""The simulated platforms: ``development`` and ``test`` (MPF: ``smart_virtual`` and ``virtual``).

Both accept any switch, coil and light number and record what's done to
them. They differ in one thing:

- **development** simulates a working machine: when a trough's eject coil
  fires, a ball leaves the trough by itself.
- **test** does nothing on its own. Every switch change is explicit, made by
  the test (or the test harness).
"""

from dataclasses import dataclass, field
from typing import Any, ClassVar

from vukery.core.log import Logs
from vukery.platforms.interfaces import (
    DriverConfig,
    DriverSettings,
    HoldSettings,
    LightPlatformInterface,
    PlatformHost,
    PulseSettings,
    SwitchConfig,
    SwitchSettings,
)


@dataclass
class SimSwitch:
    number: int
    label: str
    config: SwitchConfig


@dataclass
class SimDriver:
    platform: SimulatedPlatform
    number: int
    label: str
    config: DriverConfig
    pulses: list[PulseSettings] = field(default_factory=list[PulseSettings])
    enabled: HoldSettings | None = None

    def pulse(self, pulse_settings: PulseSettings) -> None:
        self.pulses.append(pulse_settings)
        self.platform.driver_fired(self)

    def timed_enable(self, pulse_settings: PulseSettings, hold_settings: HoldSettings) -> None:
        self.pulses.append(pulse_settings)
        self.enabled = hold_settings
        self.platform.driver_fired(self)

    def enable(self, pulse_settings: PulseSettings, hold_settings: HoldSettings) -> None:
        self.enabled = hold_settings
        self.platform.driver_fired(self)

    def disable(self) -> None:
        self.enabled = None


class SimLight(LightPlatformInterface):
    """One simulated light channel. Keeps its brightness so views and tests can read it."""

    def __init__(self, number: str, host: PlatformHost):
        super().__init__(number)
        self.host = host
        self.fade = (0.0, 0.0, 0.0, -1.0)

    def set_fade(self, start_brightness: float, start_time: float, target_brightness: float,
                 target_time: float) -> None:
        self.fade = (start_brightness, start_time, target_brightness, target_time)

    @property
    def brightness(self) -> float:
        start, start_time, target, target_time = self.fade
        now = self.host.now()
        if target_time < 0 or now >= target_time:
            return target
        return start + (target - start) * (now - start_time) / (target_time - start_time)

    def get_successor_number(self) -> str:
        led, channel = self.number.rsplit("-", 1)
        return f"{led}-{int(channel) + 1}" if int(channel) < 2 else f"{_next(led)}-0"

    def __lt__(self, other: SimLight) -> bool:
        return _sort_key(self.number) < _sort_key(other.number)


def _next(led: str) -> str:
    return str(int(led) + 1) if led.isdigit() else f"{led}+"


def _sort_key(number: str) -> tuple[str, int]:
    led, channel = number.rsplit("-", 1)
    return (led.zfill(8), int(channel))


class SimulatedPlatform(Logs):
    """A platform with no hardware behind it."""

    features: ClassVar[dict[str, int]] = {"max_pulse": 255}

    def __init__(self, host: PlatformHost, simulate_balls: bool):
        self.host = host
        self.simulate_balls = simulate_balls
        self.configure_logging("platforms.simulated")
        self.switches: dict[str, SimSwitch] = {}
        self.drivers: dict[str, SimDriver] = {}
        self.lights: dict[str, SimLight] = {}
        self.rules: dict[tuple[int, int], str] = {}  # (switch number, driver number) -> rule
        self._driver_listeners: dict[int, list[Any]] = {}

    def __repr__(self) -> str:
        return f"<SimulatedPlatform {'development' if self.simulate_balls else 'test'}>"

    # --- lifecycle (nothing to connect to)

    async def initialize(self) -> None: ...

    async def soft_reset(self) -> None: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    # --- configuration

    def configure_switch(self, number: str, config: SwitchConfig, platform_settings: dict[str, Any] | None = None
                         ) -> SimSwitch:
        switch = SimSwitch(len(self.switches), number, config)
        self.switches[number] = switch
        return switch

    def configure_driver(self, config: DriverConfig, number: str, platform_settings: dict[str, Any] | None = None
                         ) -> SimDriver:
        driver = SimDriver(self, len(self.drivers), number, config)
        self.drivers[number] = driver
        return driver

    def parse_light_number_to_channels(self, number: str, subtype: str | None = None) -> list[dict[str, str]]:
        return [{"number": f"{number}-{i}"} for i in range(3)]

    def configure_light(self, number: str, subtype: str | None = None, config: Any = None,
                        platform_settings: dict[str, Any] | None = None) -> SimLight:
        light = SimLight(number, self.host)
        self.lights[number] = light
        return light

    # --- hardware rules: recorded; in development, a rule fires its coil when its switch closes

    def set_pulse_on_hit_rule(self, enable_switch: SwitchSettings, coil: DriverSettings) -> None:
        self.rules[(enable_switch.hw_switch.number, coil.hw_driver.number)] = "pulse_on_hit"

    def set_pulse_on_hit_and_enable_and_release_rule(self, enable_switch: SwitchSettings,
                                                     coil: DriverSettings) -> None:
        self.rules[(enable_switch.hw_switch.number, coil.hw_driver.number)] = "pulse_on_hit_and_enable_and_release"

    def set_pulse_on_hit_and_release_rule(self, enable_switch: SwitchSettings, coil: DriverSettings) -> None:
        self.rules[(enable_switch.hw_switch.number, coil.hw_driver.number)] = "pulse_on_hit_and_release"

    def set_pulse_on_hit_and_release_and_disable_rule(self, enable_switch: SwitchSettings, eos_switch: SwitchSettings,
                                                      coil: DriverSettings, repulse_settings: Any = None) -> None:
        self.rules[(enable_switch.hw_switch.number, coil.hw_driver.number)] = "pulse_on_hit_and_release_and_disable"

    def set_pulse_on_hit_and_enable_and_release_and_disable_rule(self, enable_switch: SwitchSettings,
                                                                 eos_switch: SwitchSettings, coil: DriverSettings,
                                                                 repulse_settings: Any = None) -> None:
        self.rules[(enable_switch.hw_switch.number, coil.hw_driver.number)] = \
            "pulse_on_hit_and_enable_and_release_and_disable"

    def clear_hw_rule(self, switch: SwitchSettings, coil: DriverSettings) -> None:
        self.rules.pop((switch.hw_switch.number, coil.hw_driver.number), None)

    # --- simulation

    def set_switch(self, number: str, state: int) -> None:
        """Change a switch, as if the ball or a player did it."""
        self.host.switch_changed(self, self.switches[number].number, 1 if state else 0)

    def on_driver_fired(self, driver: SimDriver, listener: Any) -> None:
        """Call ``listener(driver)`` whenever ``driver`` fires (used to simulate ball devices)."""
        self._driver_listeners.setdefault(driver.number, []).append(listener)

    def driver_fired(self, driver: SimDriver) -> None:
        for listener in self._driver_listeners.get(driver.number, []):
            listener(driver)
