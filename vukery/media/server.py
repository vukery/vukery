"""The engine's side of the media protocol: decides what each display shows.

Modes show scenes with a priority (the mode's priority plus their own, as in
MPF's ``slide_player``). Each display shows its highest-priority scene, and a
mode's scenes go away when it stops. Media controllers are told only what
changed.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from itertools import count
from typing import TYPE_CHECKING, Any

from vukery.core.errors import ConfigError
from vukery.core.log import Logs
from vukery.media import dashboard, protocol
from vukery.media.scenes import Scene

if TYPE_CHECKING:
    from vukery.core.machine import Machine
    from vukery.core.modes import Mode


@dataclass(frozen=True)
class DisplayConfig:
    """One entry of the ``displays:`` section (MPF's name)."""

    name: str
    width: int = 800
    height: int = 480
    screen: int | None = None  # which monitor vuk us puts it on, full screen (default: the next one)

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any]) -> DisplayConfig:
        unknown = sorted(set(data) - {"width", "height", "screen"})
        if unknown:
            raise ConfigError(f"displays: {name}: not supported yet: {', '.join(unknown)}")
        screen = data.get("screen")
        return cls(name=name, width=int(data.get("width", 800)), height=int(data.get("height", 480)),
                   screen=None if screen is None else int(screen))


@dataclass
class _Shown:
    scene: str
    display: str
    priority: int
    mode: str
    order: int


def _jsonable(value: Any) -> bool:
    try:
        json.dumps(value)
    except TypeError:
        return False
    return True


STATE_SECONDS = 1 / 20  # how often dashboards are told what changed


class MediaServer(Logs):
    """Tracks what each display shows and keeps media controllers up to date."""

    def __init__(self, machine: Machine, displays: dict[str, DisplayConfig], port: int):
        self.machine = machine
        self.displays = displays
        self.port = port
        self.scenes: dict[str, dict[str, Any]] = {}   # name -> the scene, as data
        self.showing: dict[str, str | None] = {name: None for name in displays}
        self._stack: list[_Shown] = []
        self._order = count()
        self._clients: list[Callable[[dict[str, Any]], None]] = []
        self._dashboards: list[Callable[[dict[str, Any]], None]] = []
        self._last_state: dict[str, Any] | None = None
        self._poller: Any = None
        self._server: asyncio.Server | None = None
        self.configure_logging("media")
        machine.events.monitors.append(self._event_posted)

    @property
    def default_display(self) -> str:
        return next(iter(self.displays))

    # --- scenes

    def define(self, name: str, scene: Scene, mode: str) -> None:
        if name in self.scenes:
            raise ConfigError(f"Scene {name!r} is defined twice (again in mode {mode})")
        self.scenes[name] = scene.to_data()

    def show(self, mode: Mode, scene: str, display: str | None = None, priority: int = 0) -> None:
        if not self.displays:
            return  # running for the dashboard only, with no displays to show scenes on
        if scene not in self.scenes:
            raise ConfigError(f"Mode {mode.name} shows scene {scene!r}, which isn't defined "
                              "(list its function in the mode's scenes)")
        display = display or self.default_display
        if display not in self.displays:
            raise ConfigError(f"Mode {mode.name} shows scene {scene!r} on display {display!r}, "
                              f"which isn't in displays: ({', '.join(self.displays)})")
        self._stack = [s for s in self._stack if not (s.scene == scene and s.display == display)]
        self._stack.append(_Shown(scene, display, mode.priority + priority, mode.name, next(self._order)))
        self._update(display)

    def remove(self, mode: Mode, scene: str | None = None) -> None:
        """Remove one of a mode's scenes, or all of them."""
        touched = {s.display for s in self._stack if s.mode == mode.name and scene in (None, s.scene)}
        self._stack = [s for s in self._stack if not (s.mode == mode.name and scene in (None, s.scene))]
        for display in touched:
            self._update(display)

    def _update(self, display: str) -> None:
        candidates = [s for s in self._stack if s.display == display]
        top = max(candidates, key=lambda s: (s.priority, s.order)).scene if candidates else None
        if self.showing.get(display) != top:
            self.showing[display] = top
            self._send({"type": "show", "display": display, "scene": top})

    # --- game state for widgets

    def _event_posted(self, event: str, kwargs: dict[str, Any]) -> None:
        match event, kwargs:
            case "player_turn_started", {"number": int() as number}:
                self._send({"type": "turn", "number": number})
            case "game_ended", _:
                self._send({"type": "turn", "number": None})
            case "player_added", {"player": player, "number": int() as number}:
                # a new player's starting values (score 0...) never "change", so send them all
                self._send({"type": "player", "number": number,
                            "vars": {k: v for k, v in player.vars.items() if _jsonable(v)}})
            case str() as name, {"player_num": int() as number, "value": value} if name.startswith("player_"):
                if _jsonable(value):
                    self._send({"type": "player", "number": number, "vars": {name[len("player_"):]: value}})
            case _:
                pass

    def welcome(self) -> dict[str, Any]:
        game = self.machine.game
        players = {str(p.number): {k: v for k, v in p.vars.items() if _jsonable(v)}
                   for p in (game.players if game else [])}
        return {
            "type": "welcome",
            "version": protocol.VERSION,
            "displays": {name: {"width": d.width, "height": d.height} for name, d in self.displays.items()},
            "scenes": dict(self.scenes),
            "showing": dict(self.showing),
            "player": game.player.number if game and game.player else None,
            "players": players,
        }

    # --- clients

    def attach(self, receive: Callable[[dict[str, Any]], None], dashboard: bool = False) -> None:
        """Connect an in-process media controller or dashboard (tests). It gets the welcome right away."""
        self._add_client(receive, dashboard)

    def _add_client(self, receive: Callable[[dict[str, Any]], None], is_dashboard: bool) -> None:
        self._clients.append(receive)
        welcome = self.welcome()
        if is_dashboard:
            self._dashboards.append(receive)
            state = dashboard.snapshot(self.machine)
            self._last_state = state
            welcome |= {"dashboard": dashboard.layout(self.machine), "state": state}
            if self._poller is None:
                self._poller = self.machine.schedule_interval(self.send_state, STATE_SECONDS)
        receive(welcome)

    def _remove_client(self, receive: Callable[[dict[str, Any]], None]) -> None:
        for clients in (self._clients, self._dashboards):
            if receive in clients:
                clients.remove(receive)

    def send_state(self) -> None:
        """Tell dashboards the machine's state, if it changed since last time."""
        if not self._dashboards:
            return
        state = dashboard.snapshot(self.machine)
        if state != self._last_state:
            self._last_state = state
            for receive in list(self._dashboards):
                receive({"type": "state", **state})

    def handle(self, message: dict[str, Any], from_dashboard: bool) -> None:
        """A message from a media controller or dashboard.

        The only one acted on is a dashboard's switch change, on the simulated
        platforms. Nothing a client sends can fire a coil.
        """
        match message:
            case {"type": "switch", "name": str() as name, "state": 0 | 1 as state} if from_dashboard:
                if not self.machine.platform_is_simulated():
                    self.warning_log("Ignoring switch %s from the dashboard: switches come from the hardware", name)
                elif name not in self.machine.switches.switches:
                    self.warning_log("Ignoring switch %s from the dashboard: no such switch", name)
                else:
                    self.machine.set_switch(name, state)
            case _:
                self.debug_log("Ignoring a message from a media controller: %s", message)

    def _send(self, message: dict[str, Any]) -> None:
        for receive in list(self._clients):
            receive(message)

    async def serve(self) -> None:
        self._server = await asyncio.start_server(self._connection, "127.0.0.1", self.port)
        self.info_log("Media controllers can connect on 127.0.0.1:%s", self.port)

    async def _connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        def receive(message: dict[str, Any]) -> None:
            writer.write(protocol.encode(message))

        try:
            hello = protocol.decode(await reader.readline())
            if hello.get("type") != "hello" or hello.get("version") != protocol.VERSION:
                self.warning_log("Refusing a media controller: %s", hello)
                writer.close()
                return
            is_dashboard = hello.get("dashboard") is True
            self.info_log("%s connected: displays %s", "Dashboard" if is_dashboard else "Media controller",
                          hello.get("displays"))
            self._add_client(receive, is_dashboard)
            while line := await reader.readline():
                self.handle(protocol.decode(line), is_dashboard)
        except (ConnectionError, ValueError) as e:
            self.warning_log("Media controller connection failed: %s", e)
        finally:
            self._remove_client(receive)
            writer.close()
            self.info_log("Media controller disconnected")

    def stop(self) -> None:
        self._send({"type": "bye"})
        if self._server:
            self._server.close()
