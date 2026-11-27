"""``vuk me``'s keyboard: keys from the machine's ``keyboard:`` section press switches and post events.

``KeyboardInput`` decides what a key does; the window only says which key
went down or up (``key_name``). Keys only work on the simulated platforms,
as clicks do: the engine refuses them on real hardware.
"""

from collections.abc import Callable
from typing import Any

from vukery.dashboard.state import DashboardState
from vukery.media.keyboard import ALIASES

MOD_SHIFT, MOD_CTRL, MOD_ALT = 1, 2, 4   # pyglet's modifier bits


def key_name(symbol: int, modifiers: int, symbol_string: Callable[[int], str] | None = None) -> str:
    """A pyglet key press as a ``keyboard:`` name: ``"z"``, ``"/"``, ``"ctrl+l"``, ``"space"``."""
    if 32 < symbol < 127:   # pyglet's codes for printable keys are their (lowercase) characters
        base = chr(symbol)
    else:
        if symbol_string is None:
            from pyglet.window import key

            symbol_string = key.symbol_string
        base = symbol_string(symbol).lower().lstrip("_")
    base = ALIASES.get(base, base)
    held = [name for name, bit in (("ctrl", MOD_CTRL), ("shift", MOD_SHIFT), ("alt", MOD_ALT)) if modifiers & bit]
    return "+".join([*held, base])


class KeyboardInput:
    def __init__(self, state: DashboardState, send: Callable[[dict[str, Any]], None]) -> None:
        self.state = state
        self.send = send
        self.held: dict[int, str] = {}   # key code -> the binding it pressed, so releasing it matches
        self._layout_version = -1

    @property
    def keys(self) -> dict[str, dict[str, Any]]:
        return dict(self.state.layout.get("keyboard") or {})

    def sync(self) -> None:
        """When a (new) layout arrives: inverted switches start active, until their key is pressed."""
        if self.state.layout_version == self._layout_version:
            return
        self._layout_version = self.state.layout_version
        self.held = {}
        for key in self.keys.values():
            if key.get("switch") and key.get("invert") and not key.get("toggle"):
                self._switch(key["switch"], 1)

    def press(self, symbol: int, name: str) -> None:
        key = self.keys.get(name)
        if key is None or symbol in self.held:   # not a binding, or the key repeating
            return
        self.held[symbol] = name
        match key:
            case {"switch": str() as switch, "toggle": True}:
                self._switch(switch, 0 if self.state.switch(switch) else 1)
            case {"switch": str() as switch}:
                self._switch(switch, 0 if key.get("invert") else 1)
            case {"event": str() as event}:
                if self.state.layout.get("switch_input"):
                    self.send({"type": "event", "name": event, "params": dict(key.get("params") or {})})
            case _:
                pass

    def release(self, symbol: int) -> None:
        key = self.keys.get(self.held.pop(symbol, ""))
        match key:
            case {"switch": str() as switch} if not key.get("toggle"):
                self._switch(switch, 1 if key.get("invert") else 0)
            case _:
                pass

    def _switch(self, switch: str, state: int) -> None:
        if self.state.layout.get("switch_input"):   # simulated platforms only, as clicks
            self.send({"type": "switch", "name": switch, "state": state})
