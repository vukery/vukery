"""Ball devices (MPF: ``ball_devices:``), starting with the simplest one: a trough.

A first, deliberately simple version: it counts balls by its switches,
ejects with its coil, and reports drains. MPF's full ball device logic
(eject confirmation and retries, jams, lost balls, ball search) is ported
later.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vukery.core.errors import ConfigError
from vukery.core.log import Logs
from vukery.core.yaml_values import names

if TYPE_CHECKING:
    from vukery.core.machine import Machine

SIMULATED_EJECT_SECONDS = 0.1


@dataclass(frozen=True)
class BallDeviceConfig:
    """One entry of the ``ball_devices:`` section. Keys match MPF."""

    name: str
    ball_switches: tuple[str, ...]
    eject_coil: str | None = None
    tags: tuple[str, ...] = ()

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any]) -> BallDeviceConfig:
        supported = {"ball_switches", "eject_coil", "tags"}
        unsupported = sorted(set(data) - supported)
        if unsupported:
            raise ConfigError(f"ball_devices: {name}: not supported yet: {', '.join(unsupported)}")

        switches = names(data.get("ball_switches"), f"ball_devices: {name}: ball_switches")
        if not switches:
            raise ConfigError(f"ball_devices: {name}: needs ball_switches")
        return cls(name=name, ball_switches=switches, eject_coil=data.get("eject_coil"), tags=names(data.get("tags"), f"ball_devices: {name}: tags"))


class Trough(Logs):
    """A trough: balls wait here between balls and games."""

    def __init__(self, config: BallDeviceConfig, machine: Machine):
        self.config = config
        self.name = config.name
        self.machine = machine
        self.configure_logging(f"devices.ball_device.{self.name}")
        for switch in config.ball_switches:
            machine.switches[switch]
            machine.events.add_handler(f"{switch}_active", self._ball_entered)
        self.coil = machine.coils[config.eject_coil] if config.eject_coil else None
        if self.coil and machine.platform_simulates_balls():
            machine.platform.on_driver_fired(self.coil.hw_driver, self._simulate_eject)

    @property
    def balls(self) -> int:
        return sum(1 for s in self.config.ball_switches if self.machine.switches[s].state)

    @property
    def capacity(self) -> int:
        return len(self.config.ball_switches)

    @property
    def is_full(self) -> bool:
        return self.balls >= self.capacity

    def eject(self) -> bool:
        """Kick one ball out. Returns False if there's no ball or no eject coil."""
        if not self.coil or self.balls == 0:
            self.warning_log("Can't eject: %s", "no eject coil" if not self.coil else "no balls")
            return False
        self.coil.pulse()
        return True

    def _ball_entered(self, **_: Any) -> None:
        game = self.machine.game
        if game and game.balls_in_play > 0:
            self.machine.events.post_relay("ball_drain", balls=1, device=self.name)

    def _simulate_eject(self, _driver: Any) -> None:
        """development: the ball rolls out of the eject position (the first switch with a ball)."""
        for switch in self.config.ball_switches:
            if self.machine.switches[switch].state:
                self.machine.clock.call_later(SIMULATED_EJECT_SECONDS, self.machine.set_switch, switch, 0)
                return
