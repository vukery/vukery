"""What the ``vuk me`` dashboard knows: a media controller's state plus the machine's devices.

Built only from protocol messages, so it's testable without a screen.
"""

import time
from collections.abc import Callable
from typing import Any

from vukery.core.yaml_values import mapping
from vukery.mc.state import MediaState

FLASH_SECONDS = 0.25  # how long a pulsed coil stays lit on the dashboard


class DashboardState(MediaState):
    def __init__(self, now: Callable[[], float] = time.monotonic) -> None:
        super().__init__()
        self.now = now
        self.layout: dict[str, Any] = {}
        self.devices: dict[str, Any] = {}
        self.layout_version = 0  # goes up when the layout changes, so the view rebuilds
        self._flashed: dict[str, float] = {}

    def apply(self, message: dict[str, Any]) -> None:
        super().apply(message)
        match message:
            case {"type": "welcome", "dashboard": layout}:
                self.layout = mapping(layout)
                self.layout_version += 1
                self._set_devices(mapping(message.get("state")))
            case {"type": "state"}:
                self._set_devices({k: v for k, v in message.items() if k != "type"})
            case _:
                pass

    def _set_devices(self, devices: dict[str, Any]) -> None:
        old = mapping(self.devices.get("coils"))
        for name, coil in mapping(devices.get("coils")).items():
            if mapping(old.get(name)).get("pulses", 0) < mapping(coil).get("pulses", 0):
                self._flashed[name] = self.now()
        self.devices = devices

    # --- reading

    def switch(self, name: str) -> bool:
        return bool(mapping(self.devices.get("switches")).get(name))

    def light(self, name: str) -> str:
        return str(mapping(self.devices.get("lights")).get(name, "000000"))

    def coil_on(self, name: str) -> bool:
        """Held on, driven by a hardware rule, or pulsed in the last moment."""
        coil = mapping(mapping(self.devices.get("coils")).get(name))
        return bool(coil.get("on")) or self.now() - self._flashed.get(name, -FLASH_SECONDS) < FLASH_SECONDS

    def device_lines(self) -> list[str]:
        """The devices pane: ball devices, flippers and autofire coils."""
        lines = [f"{name}  {balls}/{capacity} balls"
                 for name, (balls, capacity) in mapping(self.devices.get("ball_devices")).items()]
        lines += [f"{name}  {'enabled' if on else 'disabled'}" for name, on in mapping(self.devices.get("rules")).items()]
        return lines

    def game_lines(self) -> list[str]:
        """The game pane: whose turn it is, every player's score, and the running modes."""
        lines: list[str] = []
        if self.current is None:
            lines.append("No game in progress")
        else:
            ball = self.players.get(self.current, {}).get("ball", "")
            lines.append(f"Player {self.current} of {len(self.players)}   Ball {ball}")
            for number in sorted(self.players):
                score = self.players[number].get("score", 0)
                marker = ">" if number == self.current else " "
                lines.append(f"{marker} P{number}  {score:,}" if isinstance(score, int) else f"{marker} P{number}  {score}")
        lines += ["", "Modes (priority)"]
        lines += [f"  {name}  {priority}" for name, priority in self.devices.get("modes", [])]
        return lines

    def game_columns(self) -> tuple[list[str], list[str]]:
        """The game section in two columns: whose turn and every score; the running modes."""
        lines = self.game_lines()
        split = lines.index("")
        return lines[:split], lines[split + 1:]

    def device_columns(self) -> tuple[list[str], list[str]]:
        """The devices section in two columns, the left one filling first."""
        lines = self.device_lines() or ["none"]
        half = -(-len(lines) // 2)
        return lines[:half], lines[half:]
