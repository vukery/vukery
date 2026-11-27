"""Ball devices (MPF: ``ball_devices:``): troughs and mechanical plunger lanes so far.

A first, deliberately simple version: a device counts balls by its switches,
ejects with its coil, and a device tagged ``drain`` reports drains. On the
simulated platforms an eject moves the ball, as MPF's smart_virtual platform
does: it leaves the device's switch, then closes the first empty switch of its
``eject_targets`` device (a ball ejected to the playfield is just gone).
MPF's full ball device logic (eject confirmation and retries, jams, lost
balls, ball search) is ported later.
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
    eject_targets: tuple[str, ...] = ("playfield",)
    mechanical_eject: bool = False   # a plunger the player pulls: the ball leaves when they shoot it
    ball_search_order: int = 200     # MPF's default; 0 leaves it out of ball search

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any]) -> BallDeviceConfig:
        supported = {"ball_switches", "eject_coil", "tags", "eject_targets", "mechanical_eject", "ball_search_order"}
        unsupported = sorted(set(data) - supported)
        if unsupported:
            raise ConfigError(f"ball_devices: {name}: not supported yet: {', '.join(unsupported)}")

        switches = names(data.get("ball_switches"), f"ball_devices: {name}: ball_switches")
        if not switches:
            raise ConfigError(f"ball_devices: {name}: needs ball_switches")
        targets = names(data.get("eject_targets"), f"ball_devices: {name}: eject_targets") or ("playfield",)
        return cls(name=name, ball_switches=switches, eject_coil=data.get("eject_coil"),
                   tags=names(data.get("tags"), f"ball_devices: {name}: tags"), eject_targets=targets,
                   mechanical_eject=bool(data.get("mechanical_eject", False)),
                   ball_search_order=int(data.get("ball_search_order", 200)))


class BallDevice(Logs):
    """A trough (balls wait here between balls and games) or a mechanical plunger lane."""

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
        # MPF's event; nothing claims balls yet (ball save will), so every new ball is unclaimed
        self.machine.events.post(f"balldevice_{self.name}_ball_enter", new_balls=1, unclaimed_balls=1,
                                 device=self.name)
        if "drain" in self.config.tags and game and game.balls_in_play > 0:
            self.machine.events.post_relay("ball_drain", balls=1, device=self.name)

    def _simulate_eject(self, _driver: Any) -> None:
        """Simulated: the ball rolls out of the eject position (the first switch with a ball),
        then into its eject target, if that's a ball device."""
        for switch in self.config.ball_switches:
            if self.machine.switches[switch].state:
                self.machine.clock.call_later(SIMULATED_EJECT_SECONDS, self.machine.set_switch, switch, 0)
                target = self.machine.ball_devices.get(self.config.eject_targets[0])
                if target is not None:
                    self.machine.clock.call_later(2 * SIMULATED_EJECT_SECONDS, target.receive_simulated_ball)
                return

    def ball_search(self, phase: int, iteration: int) -> bool:
        """MPF's default ball device search: phase 1, pulse if empty; then pulse anyway, except the trough."""
        if self.coil is None or "no-eject-on-ballsearch" in self.config.tags:
            return False
        if phase == 1 and self.balls > 0:
            return False
        if phase > 1 and "trough" in self.config.tags:
            return False
        self.coil.pulse()
        return True

    def receive_simulated_ball(self) -> None:
        """Simulated: a ball arrives, on the first empty ball switch (none if it's full)."""
        for switch in self.config.ball_switches:
            if not self.machine.switches[switch].state:
                self.machine.set_switch(switch, 1)
                return
        self.warning_log("A simulated ball arrived, but the device is full")
