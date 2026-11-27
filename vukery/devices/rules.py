"""Flippers (MPF: ``flippers:``) and autofire coils (MPF: ``autofire_coils:``).

Both are hardware rules: the controller fires the coil when the switch
closes, without waiting for vukery. They're switched on at ``ball_started``
and off at ``ball_will_end`` and ``service_mode_entered``, MPF's defaults.

Flippers: single- and dual-wound, with or without an EOS switch, as MPF's.
Autofire coils: plain ones (slingshots, pop bumpers).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vukery.core.errors import ConfigError
from vukery.core.log import Logs
from vukery.core.shows import seconds
from vukery.core.yaml_values import names
from vukery.platforms.interfaces import (
    DriverSettings,
    HoldSettings,
    PulseSettings,
    RepulseSettings,
    SwitchSettings,
)

if TYPE_CHECKING:
    from vukery.core.machine import Machine
    from vukery.devices.coil import Coil

DEFAULT_ENABLE = ("ball_started",)
NO_REPULSE = RepulseSettings(enable_repulse=False, debounce_ms=500)   # MPF's defaults
DEFAULT_DISABLE = ("ball_will_end", "service_mode_entered")


def _ms(value: Any, where: str) -> int:
    """MPF's ms settings: a number is milliseconds; "500ms" or "0.5s" also work."""
    return int(value) if isinstance(value, int | float) and not isinstance(value, bool) else round(seconds(value, where) * 1000)


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
        unsupported = sorted(set(data) - {"coil", "switch", "reverse_switch", "enable_events", "disable_events",
                                          "ball_search_order"})
        if unsupported:
            raise ConfigError(f"autofire_coils: {name}: not supported yet: {', '.join(unsupported)}")
        autofire = cls(RuleConfig(name=name, coil=data["coil"], switch=data["switch"],
                                  reverse_switch=bool(data.get("reverse_switch", False)),
                                  enable_events=_events(data.get("enable_events"), DEFAULT_ENABLE),
                                  disable_events=_events(data.get("disable_events"), DEFAULT_DISABLE)), machine)
        autofire.ball_search_order = int(data.get("ball_search_order", 100))   # MPF's default; 0: left out
        return autofire

    ball_search_order = 100
    _searched_until = 0.0

    def ball_search(self, phase: int, iteration: int) -> bool:
        """Pulse the coil; a hit on its switch in the next 200 ms is the pulse, not the ball (as MPF's)."""
        self._searched_until = self.machine.clock.now() + 0.2
        self.coil.pulse()
        return True

    def hit_by_ball(self) -> bool:
        """Whether a hit on its switch now is the ball (not ball search's own pulse)."""
        return self.machine.clock.now() >= self._searched_until

    def _driver_settings(self) -> DriverSettings:
        return DriverSettings(hw_driver=self.coil.hw_driver,
                              pulse_settings=PulseSettings(power=self.coil.pulse_power(), duration=self.coil.pulse_ms()),
                              hold_settings=None, recycle=True)

    def enable(self) -> None:
        if not self.enabled:
            self.machine.platform.set_pulse_on_hit_rule(*self._settings())
            self.enabled = True


class Flipper(_Rule):
    """A flipper, as MPF's: the button fires the coils through hardware rules.

    | Flipper | Main coil | Hold coil |
    |---|---|---|
    | single-wound | pulse, then hold, until the button opens | |
    | dual-wound | pulse until the button opens | pulse, then hold, until the button opens |
    | dual-wound, ``use_eos`` | pulse until the button opens or EOS closes | pulse, then hold, until it opens |
    | single-wound, ``use_eos`` | pulse, then hold; EOS closing cuts it to hold | |

    ``repulse_on_eos_open`` (with ``eos_active_ms_before_repulse``) pulses the
    main coil again when EOS opens while the button is held: the ball knocked
    the flipper down.
    """

    kind = "flipper"
    SETTINGS = frozenset({"main_coil", "hold_coil", "activation_switch", "eos_switch", "use_eos", "repulse_on_eos_open",
                          "eos_active_ms_before_repulse", "enable_events", "disable_events", "label"})

    def __init__(self, config: RuleConfig, machine: Machine, hold_coil: str | None = None,
                 eos_switch: str | None = None, use_eos: bool = False,
                 repulse: RepulseSettings = NO_REPULSE,
                 label: str | None = None):
        super().__init__(config, machine)
        self.hold_coil = machine.coils[hold_coil] if hold_coil else None
        self.eos_switch = machine.switches[eos_switch] if eos_switch else None
        self.use_eos = use_eos
        self.repulse = repulse
        self.label = label or config.name
        holder = self.hold_coil or self.coil
        if self.hold_coil is not None and not self.hold_coil.hold_power():
            raise ConfigError(f"flippers: {config.name}: hold_coil {self.hold_coil.name} can't be held on: give it "
                              "default_hold_power, max_hold_power or allow_enable: true")
        self._holder = holder

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any], machine: Machine) -> Flipper:
        unsupported = sorted(set(data) - cls.SETTINGS)
        if unsupported:
            raise ConfigError(f"flippers: {name}: not supported yet: {', '.join(unsupported)}")
        use_eos = bool(data.get("use_eos", False))
        if use_eos and not data.get("eos_switch"):
            raise ConfigError(f"flippers: {name}: use_eos needs an eos_switch")
        repulse = RepulseSettings(enable_repulse=bool(data.get("repulse_on_eos_open", False)),
                                  debounce_ms=_ms(data.get("eos_active_ms_before_repulse", 500),
                                                  f"flippers: {name}: eos_active_ms_before_repulse"))
        return cls(RuleConfig(name=name, coil=data["main_coil"], switch=data["activation_switch"],
                              enable_events=_events(data.get("enable_events"), DEFAULT_ENABLE),
                              disable_events=_events(data.get("disable_events"), DEFAULT_DISABLE)), machine,
                   hold_coil=data.get("hold_coil"), eos_switch=data.get("eos_switch"), use_eos=use_eos,
                   repulse=repulse, label=data.get("label"))

    @property
    def dual_wound(self) -> bool:
        return self.hold_coil is not None

    def coils(self) -> list[Coil]:
        return [self.coil, *([self.hold_coil] if self.hold_coil is not None else [])]

    def _driver(self, coil: Coil, hold: bool) -> DriverSettings:
        power = coil.hold_power() if hold else None
        return DriverSettings(hw_driver=coil.hw_driver,
                              pulse_settings=PulseSettings(power=coil.pulse_power(), duration=coil.pulse_ms()),
                              hold_settings=HoldSettings(power=power) if power else None, recycle=False)

    def _driver_settings(self) -> DriverSettings:
        return self._driver(self.coil, hold=not self.dual_wound)

    def _switch(self, switch: Any) -> SwitchSettings:
        return SwitchSettings(hw_switch=switch.hw, invert=switch.invert, debounce=False)

    def enable(self) -> None:
        if self.enabled:
            return
        platform = self.machine.platform
        button = self._switch(self.switch)
        match self.dual_wound, self.use_eos:
            case True, True:
                platform.set_pulse_on_hit_and_release_and_disable_rule(
                    button, self._switch(self.eos_switch), self._driver(self.coil, hold=False), self.repulse)
            case True, False:
                platform.set_pulse_on_hit_and_release_rule(button, self._driver(self.coil, hold=False))
            case False, True:
                platform.set_pulse_on_hit_and_enable_and_release_and_disable_rule(
                    button, self._switch(self.eos_switch), self._driver(self.coil, hold=True), self.repulse)
            case _:
                platform.set_pulse_on_hit_and_enable_and_release_rule(button, self._driver(self.coil, hold=True))
        if self.hold_coil is not None:
            platform.set_pulse_on_hit_and_enable_and_release_rule(button, self._driver(self.hold_coil, hold=True))
        self.enabled = True

    def disable(self) -> None:
        """Clear every rule it set, as MPF's does: the button's and EOS's on the main coil, the button's on the hold coil."""
        if not self.enabled:
            return
        platform = self.machine.platform
        main = self._driver(self.coil, hold=not self.dual_wound)
        platform.clear_hw_rule(self._switch(self.switch), main)
        if self.use_eos and self.eos_switch is not None:
            platform.clear_hw_rule(self._switch(self.eos_switch), main)
        if self.hold_coil is not None:
            platform.clear_hw_rule(self._switch(self.switch), self._driver(self.hold_coil, hold=True))
        self.enabled = False

    def driven(self) -> set[str]:
        """The coils its rules hold on right now (for vuk me): the hold coil while the button is down,
        and the main coil until EOS closes."""
        if not (self.enabled and self.switch.state):
            return set()
        on: set[str] = {self.hold_coil.name} if self.hold_coil is not None else set()
        if not (self.use_eos and self.eos_switch is not None and self.eos_switch.state and self.dual_wound):
            on.add(self.coil.name)
        return on
