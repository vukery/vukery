"""Flippers (MPF: ``flippers:``) and autofire coils (MPF: ``autofire_coils:``).

Both are hardware rules: the controller fires the coil when the switch
closes, without waiting for vukery. They're switched on at ``ball_started``
and off at ``ball_will_end`` and ``service_mode_entered``, MPF's defaults.

This first version covers single-wound flippers without an EOS switch, and
plain autofire coils (slingshots, pop bumpers).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vukery.core.errors import ConfigError
from vukery.core.log import Logs
from vukery.core.yaml_values import names
from vukery.platforms.interfaces import DriverSettings, HoldSettings, PulseSettings, SwitchSettings

if TYPE_CHECKING:
    from vukery.core.machine import Machine

DEFAULT_ENABLE = ("ball_started",)
DEFAULT_DISABLE = ("ball_will_end", "service_mode_entered")


def _events(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    return default if value is None else names(value, "enable_events / disable_events")


@dataclass(frozen=True)
class RuleConfig:
    name: str
    coil: str
    switch: str
    reverse_switch: bool = False
    enable_events: tuple[str, ...] = DEFAULT_ENABLE
    disable_events: tuple[str, ...] = DEFAULT_DISABLE


class _Rule(Logs):
    kind = "rule"

    def __init__(self, config: RuleConfig, machine: Machine):
        self.config = config
        self.name = config.name
        self.machine = machine
        self.enabled = False
        self.configure_logging(f"devices.{self.kind}.{self.name}")
        self.coil = machine.coils[config.coil]
        self.switch = machine.switches[config.switch]
        for event in config.enable_events:
            machine.events.add_handler(event, self._on_enable_event)
        for event in config.disable_events:
            machine.events.add_handler(event, self._on_disable_event)

    def _on_enable_event(self, **_: Any) -> None:
        self.enable()

    def _on_disable_event(self, **_: Any) -> None:
        self.disable()

    def _settings(self) -> tuple[SwitchSettings, DriverSettings]:
        switch = SwitchSettings(hw_switch=self.switch.hw, invert=self.switch.invert ^ self.config.reverse_switch,
                                debounce=False)
        return switch, self._driver_settings()

    def _driver_settings(self) -> DriverSettings:
        raise NotImplementedError

    def enable(self) -> None:
        raise NotImplementedError

    def disable(self) -> None:
        if self.enabled:
            self.machine.platform.clear_hw_rule(*self._settings())
            self.enabled = False


class AutofireCoil(_Rule):
    """Fires its coil whenever its switch closes (slingshots, pop bumpers)."""

    kind = "autofire"

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any], machine: Machine) -> AutofireCoil:
        unsupported = sorted(set(data) - {"coil", "switch", "reverse_switch", "enable_events", "disable_events"})
        if unsupported:
            raise ConfigError(f"autofire_coils: {name}: not supported yet: {', '.join(unsupported)}")
        return cls(RuleConfig(name=name, coil=data["coil"], switch=data["switch"],
                              reverse_switch=bool(data.get("reverse_switch", False)),
                              enable_events=_events(data.get("enable_events"), DEFAULT_ENABLE),
                              disable_events=_events(data.get("disable_events"), DEFAULT_DISABLE)), machine)

    def _driver_settings(self) -> DriverSettings:
        return DriverSettings(hw_driver=self.coil.hw_driver,
                              pulse_settings=PulseSettings(power=self.coil.pulse_power(), duration=self.coil.pulse_ms()),
                              hold_settings=None, recycle=True)

    def enable(self) -> None:
        if not self.enabled:
            self.machine.platform.set_pulse_on_hit_rule(*self._settings())
            self.enabled = True


class Flipper(_Rule):
    """A single-wound flipper: pulse when the button closes, hold, release when it opens."""

    kind = "flipper"

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any], machine: Machine) -> Flipper:
        later = sorted(set(data) & {"hold_coil", "eos_switch", "use_eos"})
        if later:
            raise ConfigError(f"flippers: {name}: {', '.join(later)} isn't supported yet "
                              "(only single-wound flippers without EOS)")
        unsupported = sorted(set(data) - {"main_coil", "activation_switch", "enable_events", "disable_events"})
        if unsupported:
            raise ConfigError(f"flippers: {name}: not supported yet: {', '.join(unsupported)}")
        return cls(RuleConfig(name=name, coil=data["main_coil"], switch=data["activation_switch"],
                              enable_events=_events(data.get("enable_events"), DEFAULT_ENABLE),
                              disable_events=_events(data.get("disable_events"), DEFAULT_DISABLE)), machine)

    def _driver_settings(self) -> DriverSettings:
        hold = self.coil.hold_power()
        return DriverSettings(hw_driver=self.coil.hw_driver,
                              pulse_settings=PulseSettings(power=self.coil.pulse_power(), duration=self.coil.pulse_ms()),
                              hold_settings=HoldSettings(power=hold) if hold else None, recycle=False)

    def enable(self) -> None:
        if not self.enabled:
            self.machine.platform.set_pulse_on_hit_and_enable_and_release_rule(*self._settings())
            self.enabled = True
