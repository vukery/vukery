"""The engine's side of the media protocol: decides what each display shows.

Modes show slides with a priority (the mode's priority plus their own, as in
MPF's ``slide_player``). Each display shows its highest-priority slide, and a
mode's slides go away when it stops. Media controllers are told only what
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
from vukery.media import protocol
from vukery.media.slides import Slide

if TYPE_CHECKING:
    from vukery.core.machine import Machine
    from vukery.core.modes import Mode


@dataclass(frozen=True)
class DisplayConfig:
    """One entry of the ``displays:`` section (MPF's name)."""

    name: str
    width: int = 800
    height: int = 480

    @classmethod
    def from_yaml(cls, name: str, data: dict[str, Any]) -> DisplayConfig:
        unknown = sorted(set(data) - {"width", "height"})
        if unknown:
            raise ConfigError(f"displays: {name}: not supported yet: {', '.join(unknown)}")
        return cls(name=name, width=int(data.get("width", 800)), height=int(data.get("height", 480)))


@dataclass
class _Shown:
    slide: str
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


class MediaServer(Logs):
    """Tracks what each display shows and keeps media controllers up to date."""

    def __init__(self, machine: Machine, displays: dict[str, DisplayConfig], port: int):
        self.machine = machine
        self.displays = displays
        self.port = port
        self.slides: dict[str, Slide] = {}
        self.showing: dict[str, str | None] = {name: None for name in displays}
        self._stack: list[_Shown] = []
        self._order = count()
        self._clients: list[Callable[[dict[str, Any]], None]] = []
        self._server: asyncio.Server | None = None
        self.configure_logging("media")
        machine.events.monitors.append(self._event_posted)

    @property
    def default_display(self) -> str:
        return next(iter(self.displays))

    # --- slides

    def define(self, name: str, slide: Slide, mode: str) -> None:
        if name in self.slides:
            raise ConfigError(f"Slide {name!r} is defined twice (again in mode {mode})")
        self.slides[name] = slide

    def show(self, mode: Mode, slide: str, display: str | None = None, priority: int = 0) -> None:
        if slide not in self.slides:
            raise ConfigError(f"Mode {mode.name} shows slide {slide!r}, which isn't defined")
        display = display or self.default_display
        if display not in self.displays:
            raise ConfigError(f"Mode {mode.name} shows slide {slide!r} on display {display!r}, "
                              f"which isn't in displays: ({', '.join(self.displays)})")
        self._stack = [s for s in self._stack if not (s.slide == slide and s.display == display)]
        self._stack.append(_Shown(slide, display, mode.priority + priority, mode.name, next(self._order)))
        self._update(display)

    def remove(self, mode: Mode, slide: str | None = None) -> None:
        """Remove one of a mode's slides, or all of them."""
        touched = {s.display for s in self._stack if s.mode == mode.name and slide in (None, s.slide)}
        self._stack = [s for s in self._stack if not (s.mode == mode.name and slide in (None, s.slide))]
        for display in touched:
            self._update(display)

    def _update(self, display: str) -> None:
        candidates = [s for s in self._stack if s.display == display]
        top = max(candidates, key=lambda s: (s.priority, s.order)).slide if candidates else None
        if self.showing.get(display) != top:
            self.showing[display] = top
            self._send({"type": "show", "display": display, "slide": top})

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
            "slides": {name: slide.to_data() for name, slide in self.slides.items()},
            "showing": dict(self.showing),
            "player": game.player.number if game and game.player else None,
            "players": players,
        }

    # --- clients

    def attach(self, receive: Callable[[dict[str, Any]], None]) -> None:
        """Connect an in-process media controller (tests). It gets the welcome right away."""
        self._clients.append(receive)
        receive(self.welcome())

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
            self.info_log("Media controller connected: displays %s", hello.get("displays"))
            self._clients.append(receive)
            receive(self.welcome())
            while await reader.readline():
                pass  # nothing is expected from media controllers yet
        except (ConnectionError, ValueError) as e:
            self.warning_log("Media controller connection failed: %s", e)
        finally:
            if receive in self._clients:
                self._clients.remove(receive)
            writer.close()
            self.info_log("Media controller disconnected")

    def stop(self) -> None:
        self._send({"type": "bye"})
        if self._server:
            self._server.close()
