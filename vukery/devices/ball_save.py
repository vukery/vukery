"""Ball saves (MPF: ``ball_saves:``): give a drained ball back for a while.

A device, as MPF's: enabled by its ``enable_events`` (or ``enable()`` from a
mode), its timer runs ``active_time`` (from enabling, or from one of its
``timer_start_events``), with a hurry-up ``hurry_up_time`` before the end and
a ``grace_period`` after it. While it's enabled, a ball that drains is
claimed from ``ball_drain`` (so the game doesn't count it) and a new one is
served, up to ``balls_to_save`` (``-1``: any number), or only the last ball
in play (``only_last_ball``). It's disabled by its ``disable_events``
(``ball_will_end`` and ``service_mode_entered`` by default).

Events, MPF's: ``ball_save_<name>_enabled``, ``_timer_start``, ``_hurry_up``,
``_grace_period``, ``_saving_ball`` (``balls``, ``early_save``), ``_disabled``.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vukery.core.errors import ConfigError
from vukery.core.log import Logs
from vukery.core.shows import seconds
from vukery.core.yaml_values import names

if TYPE_CHECKING:
    from vukery.core.machine import Machine

SETTINGS = {"active_time", "hurry_up_time", "grace_period", "auto_launch", "balls_to_save", "only_last_ball",
            "eject_delay", "enable_events", "disable_events", "timer_start_events", "debug"}
LATER = {"source_playfield", "ball_locks", "early_ball_save_events", "delayed_eject_events"}


def _ms_or_seconds(value: Any, where: str) -> float:
    """MPF's ms settings: a bare number is milliseconds; ``"2s"`` and ``"500ms"`` say which."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value) / 1000
    return seconds(value, where)


@dataclass(frozen=True)
class BallSaveConfig:
    name: str
    active_time: float = 0.0     # seconds; 0: until disabled
    hurry_up_time: float = 0.0
    grace_period: float = 0.0
    auto_launch: bool = True     # no player-controlled launch yet: the ball goes to the trough's eject target
    balls_to_save: int = 1       # -1: any number
    only_last_ball: bool = False
    eject_delay: float = 0.0
    enable_events: tuple[str, ...] = ()
    disable_events: tuple[str, ...] = ("ball_will_end", "service_mode_entered")
    timer_start_events: tuple[str, ...] = ()

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any]) -> BallSaveConfig:
        where = f"ball_saves: {name}"
        if later := sorted(set(data) & LATER):
            raise ConfigError(f"{where}: not supported yet: {', '.join(later)}")
        if unknown := sorted(set(data) - SETTINGS):
            raise ConfigError(f"{where}: unknown setting(s): {', '.join(unknown)}")
        config = cls(
            name=name,
            # MPF's active_time is in seconds (template_secs); "+15s" reads as 15 s
            active_time=seconds(data.get("active_time", 0), f"{where}: active_time"),
            hurry_up_time=_ms_or_seconds(data.get("hurry_up_time", 0), f"{where}: hurry_up_time"),
            grace_period=_ms_or_seconds(data.get("grace_period", 0), f"{where}: grace_period"),
            auto_launch=bool(data.get("auto_launch", True)),
            balls_to_save=int(data.get("balls_to_save", 1)),
            only_last_ball=bool(data.get("only_last_ball", False)),
            eject_delay=_ms_or_seconds(data.get("eject_delay", 0), f"{where}: eject_delay"),
            enable_events=names(data.get("enable_events"), f"{where}: enable_events"),
            disable_events=(names(data.get("disable_events"), f"{where}: disable_events")
                            if "disable_events" in data else cls.disable_events),
            timer_start_events=names(data.get("timer_start_events"), f"{where}: timer_start_events"),
        )
        if both := sorted(set(config.timer_start_events) & set(config.enable_events)):
            raise ConfigError(f"{where}: {', '.join(both)} is in both enable_events and timer_start_events; "
                              "the timer can't start on the event that enables it: leave it out of timer_start_events")
        return config


class BallSave(Logs):
    def __init__(self, config: BallSaveConfig, machine: Machine):
        self.config = config
        self.name = config.name
        self.machine = machine
        self.configure_logging(f"devices.ball_save.{self.name}")
        self.enabled = False
        self.timer_started = False
        self.saves_remaining = 0
        self.state = "disabled"   # enabled, hurry_up, grace_period
        self._timers: list[Any] = []
        self._drain_handler: Any = None
        events = machine.events
        for event in config.enable_events:
            events.add_handler(event, self._on_enable_event)
        for event in config.disable_events:
            events.add_handler(event, self._on_disable_event, priority=1)
        for event in config.timer_start_events:
            events.add_handler(event, self._on_timer_start_event, priority=9)

    def _on_enable_event(self, **_: Any) -> None:
        self.enable()

    def _on_disable_event(self, **_: Any) -> None:
        self.disable()

    def _on_timer_start_event(self, **_: Any) -> None:
        self.timer_start()

    @property
    def unlimited(self) -> bool:
        return self.config.balls_to_save == -1

    def enable(self) -> None:
        if self.enabled:
            return
        self.enabled = True
        self.state = "enabled"
        self.saves_remaining = self.config.balls_to_save
        self.debug_log("Enabling: %s s, %s ball(s)", self.config.active_time, self.config.balls_to_save)
        self._drain_handler = self.machine.events.add_handler("ball_drain", self._ball_drained, priority=1000)
        if self.config.active_time > 0 and not self.config.timer_start_events:
            self.timer_start()
        self.machine.events.post(f"ball_save_{self.name}_enabled")

    def disable(self) -> None:
        if not self.enabled:
            return
        self.enabled = False
        self.timer_started = False
        self.state = "disabled"
        if self._drain_handler is not None:
            self.machine.events.remove_handler(self._drain_handler)
            self._drain_handler = None
        self._cancel_timers()
        self.machine.events.post(f"ball_save_{self.name}_disabled")

    def timer_start(self) -> None:
        if self.timer_started or not self.enabled:
            return
        self.timer_started = True
        self.machine.events.post(f"ball_save_{self.name}_timer_start")
        active = self.config.active_time
        if active > 0:
            later = self.machine.clock.call_later
            self._timers = [later(active + self.config.grace_period, self.disable),
                            later(active, self._grace_period),
                            later(max(active - self.config.hurry_up_time, 0), self._hurry_up)]

    def _hurry_up(self) -> None:
        self.state = "hurry_up"
        self.machine.events.post(f"ball_save_{self.name}_hurry_up")

    def _grace_period(self) -> None:
        self.state = "grace_period"
        self.machine.events.post(f"ball_save_{self.name}_grace_period")

    def _cancel_timers(self) -> None:
        for timer in self._timers:
            timer.cancel()
        self._timers = []

    def _to_save(self, drained: int) -> int:
        game = self.machine.game
        if not game or game.balls_in_play <= 0:
            return 0
        if self.config.only_last_ball and game.balls_in_play > 1:
            return 0
        count = min(drained, game.balls_in_play, 1 if self.config.only_last_ball else drained)
        return count if self.unlimited else min(count, self.saves_remaining)

    def _ball_drained(self, balls: int = 0, **_: Any) -> dict[str, Any]:
        if balls <= 0:
            return {}
        saving = self._to_save(balls)
        if saving <= 0:
            return {}
        self.info_log("Saving %s ball(s)", saving)
        self.machine.events.post(f"ball_save_{self.name}_saving_ball", balls=saving, early_save=False)
        if self.config.eject_delay > 0:
            self.machine.clock.call_later(self.config.eject_delay, self._serve, saving)
        else:
            self._serve(saving)
        if not self.unlimited:
            self.saves_remaining -= saving
            if self.saves_remaining <= 0:
                self.disable()
        return {"balls": balls - saving}

    def _serve(self, balls: int) -> None:
        trough = self.machine.trough()
        for _ in range(balls):
            if trough is None or not trough.eject():
                self.warning_log("Can't serve a saved ball: the trough has none to eject")
