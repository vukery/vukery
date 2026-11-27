"""Switches (MPF: ``switches:``) and the switch controller.

Switch events keep MPF's names, so migrated code and tests read the same:

- ``<switch>_active`` / ``<switch>_inactive`` on every change;
- for each tag: ``sw_<tag>`` and ``sw_<tag>_active`` when the switch goes
  active, ``sw_<tag>_inactive`` when it goes inactive;
- ``events_when_activated`` / ``events_when_deactivated`` from config.

Reference: MPF's switch controller and switch device,
https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/core/switch_controller.py
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from vukery.core.clock import Clock, Timer
from vukery.core.errors import ConfigError
from vukery.core.events import EventManager
from vukery.core.log import get_logger
from vukery.core.yaml_values import names
from vukery.platforms.interfaces import SwitchConfig as PlatformSwitchConfig

log = get_logger("switches")


SETTINGS = frozenset({"number", "type", "debounce", "tags", "events_when_activated", "events_when_deactivated",
                      "platform_settings", "label"})   # a switch's settings in switches:

@dataclass(frozen=True)
class SwitchConfig:
    """One entry of the ``switches:`` section. Keys match MPF."""

    name: str
    number: str
    type: str = "NO"  # NO (normally open) or NC (normally closed)
    debounce: str = "auto"  # auto, quick or normal
    tags: tuple[str, ...] = ()
    events_when_activated: tuple[str, ...] = ()
    events_when_deactivated: tuple[str, ...] = ()
    platform_settings: dict[str, Any] | None = None

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any]) -> SwitchConfig:
        unknown = sorted(set(data) - SETTINGS)
        if unknown:
            raise ConfigError(f"switches: {name}: unknown setting(s): {', '.join(unknown)}")
        match data.get("type", "NO"):
            case False:   # YAML reads a bare NO as false
                switch_type = "NO"
            case str() as text if text.upper() in ("NO", "NC"):
                switch_type = text.upper()
            case other:
                raise ConfigError(f"switches: {name}: type must be NO or NC, got {other!r}")
        return cls(
            name=name,
            number=str(data.get("number", "")),
            type=switch_type,
            debounce=str(data.get("debounce", "auto")),
            tags=names(data.get("tags"), f"switches: {name}: tags"),
            events_when_activated=names(data.get("events_when_activated"), f"switches: {name}"),
            events_when_deactivated=names(data.get("events_when_deactivated"), f"switches: {name}"),
            platform_settings=data.get("platform_settings"),
        )


@dataclass
class Switch:
    config: SwitchConfig
    hw: Any
    state: int = 0  # logical: 1 is active
    last_change: float = 0.0

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def invert(self) -> bool:
        return self.config.type == "NC"


@dataclass
class _TimedHandler:
    switch: str
    state: int
    seconds: float
    callback: Callable[[], Any]
    timer: Timer | None = field(default=None)


class SwitchController:
    """Tracks switch states and posts switch events."""

    def __init__(self, events: EventManager, clock: Clock):
        self.events = events
        self.clock = clock
        self.switches: dict[str, Switch] = {}
        self._by_hw: dict[tuple[int, int], Switch] = {}
        self._timed: list[_TimedHandler] = []

    def add(self, config: SwitchConfig, platform: Any) -> Switch:
        if config.name in self.switches:
            raise ConfigError(f"switches: {config.name} is defined twice")
        hw = platform.configure_switch(
            config.number,
            PlatformSwitchConfig(name=config.name, invert=config.type == "NC", debounce=config.debounce),
            config.platform_settings)
        switch = Switch(config, hw)
        self.switches[config.name] = switch
        self._by_hw[(id(platform), hw.number)] = switch
        return switch

    def __getitem__(self, name: str) -> Switch:
        try:
            return self.switches[name]
        except KeyError:
            raise ConfigError(f"There's no switch named {name!r}") from None

    def is_active(self, name: str, seconds: float | None = None) -> bool:
        switch = self[name]
        held = self.clock.now() - switch.last_change
        return switch.state == 1 and (seconds is None or held >= seconds)

    def tagged(self, tag: str) -> list[Switch]:
        return [s for s in self.switches.values() if tag in s.config.tags]

    # --- changes from the platform

    def hw_changed(self, platform: Any, number: int, state: int) -> None:
        """A platform reports a logical switch change."""
        switch = self._by_hw.get((id(platform), number))
        if switch is None:
            log.debug("Change on unconfigured switch %s", number)
            return
        self.set_state(switch.name, state)

    def hw_sync(self, platform: Any, hw_states: dict[int, int]) -> None:
        """A platform reports every raw switch state at once (e.g. at startup)."""
        for (platform_id, number), switch in self._by_hw.items():
            if platform_id == id(platform) and number in hw_states:
                switch.state = int(switch.invert) ^ hw_states[number]
                switch.last_change = self.clock.now()

    def set_state(self, name: str, state: int) -> None:
        """Change a switch's logical state and post its events."""
        switch = self[name]
        state = 1 if state else 0
        if switch.state == state:
            log.debug("Ignoring duplicate state %s for switch %s", state, name)
            return
        switch.state = state
        switch.last_change = self.clock.now()
        log.info("<<<<<<< %s %s >>>>>>>", name, "active" if state else "inactive")

        for timed in self._timed:
            if timed.switch == name:
                if timed.timer:
                    timed.timer.cancel()
                    timed.timer = None
                if timed.state == state:
                    timed.timer = self.clock.call_later(timed.seconds, timed.callback)

        suffix = "active" if state else "inactive"
        self.events.post(f"{name}_{suffix}")
        for tag in switch.config.tags:
            if state:
                self.events.post(f"sw_{tag}")
            self.events.post(f"sw_{tag}_{suffix}")
        for event in (switch.config.events_when_activated if state else switch.config.events_when_deactivated):
            self.events.post(event)

    def add_timed_handler(self, name: str, callback: Callable[[], Any], seconds: float,
                          state: int = 1) -> _TimedHandler:
        """Call ``callback`` once the switch has been in ``state`` for ``seconds``."""
        self[name]
        timed = _TimedHandler(name, state, seconds, callback)
        if self.switches[name].state == state:
            remaining = max(seconds - (self.clock.now() - self.switches[name].last_change), 0.0)
            timed.timer = self.clock.call_later(remaining, callback)
        self._timed.append(timed)
        return timed

    def remove_timed_handler(self, timed: _TimedHandler) -> None:
        if timed.timer:
            timed.timer.cancel()
        if timed in self._timed:
            self._timed.remove(timed)
