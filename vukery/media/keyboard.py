"""The ``keyboard:`` section (MPF's): keys that press switches or post events in ``vuk me``.

Keys work while the dashboard window has focus, on the simulated platforms
only (as clicking does), so they can never touch real hardware::

    keyboard:
      z:
        switch: s_left_flipper     # active while the key is held
      "1":
        switch: s_trough1
        toggle: true               # each press flips it
      ctrl+l:
        event: light_all           # posted when the key goes down
        params:
          color: ffffff

A key is a character (``z``, ``/``, ``1``) or a name (``space``, ``enter``,
``left``…), with ``ctrl+``, ``shift+``, ``alt+`` in front as needed.
``invert: true`` holds a switch active until its key is pressed.
"""

from dataclasses import dataclass, field
from typing import Any

from vukery.core.errors import ConfigError
from vukery.core.yaml_values import mapping

MODIFIERS = ("ctrl", "shift", "alt")
ALIASES = {"slash": "/", "spacebar": "space", "return": "enter", "esc": "escape", "minus": "-", "equal": "=",
           "period": ".", "comma": ",", "semicolon": ";", "apostrophe": "'", "backslash": "\\"}
SETTINGS = {"switch", "toggle", "invert", "event", "params"}
SECTION_SETTINGS = {"debug"}   # MPF's keyboard: debug: true; vukery logs keys at debug level anyway


@dataclass(frozen=True)
class Key:
    name: str                    # normalized: "ctrl+shift+l"
    switch: str | None = None
    toggle: bool = False
    invert: bool = False
    event: str | None = None
    params: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {"switch": self.switch} if self.switch else {"event": self.event, "params": self.params}
        if self.toggle:
            data["toggle"] = True
        if self.invert:
            data["invert"] = True
        return data


def key_name(text: Any) -> str:
    """``"Ctrl+L"`` → ``"ctrl+l"``: modifiers first, in a fixed order, then the key."""
    parts = [part.strip().lower() for part in str(text).split("+")]
    if str(text).endswith("+") and len(str(text)) > 1:   # "ctrl++": the + key
        parts = [*parts[:-2], "+"]
    *modifiers, key = parts
    for modifier in modifiers:
        if modifier not in MODIFIERS:
            raise ConfigError(f"keyboard: {text}: {modifier!r} isn't a modifier ({', '.join(MODIFIERS)})")
    if not key:
        raise ConfigError(f"keyboard: {text!r} has no key")
    key = ALIASES.get(key, key)
    return "+".join([*(m for m in MODIFIERS if m in modifiers), key])


def load(section: dict[str, Any], switches: set[str]) -> dict[str, Key]:
    keys: dict[str, Key] = {}
    for raw, entry in section.items():
        if str(raw) in SECTION_SETTINGS:
            continue
        name = key_name(raw)
        data = mapping(entry, f"keyboard: {raw}")
        where = f"keyboard: {raw}"
        unknown = sorted(set(data) - SETTINGS)
        if unknown:
            raise ConfigError(f"{where}: not supported: {', '.join(unknown)}")
        switch, event = data.get("switch"), data.get("event")
        match switch, event:
            case None, None:
                raise ConfigError(f"{where}: give it a switch or an event")
            case str(), str():
                raise ConfigError(f"{where}: a key presses a switch or posts an event, not both")
            case str(), None if switch not in switches:
                raise ConfigError(f"{where}: no switch named {switch!r}")
            case _:
                pass
        if name in keys:
            raise ConfigError(f"{where}: the same key as another entry ({name})")
        keys[name] = Key(name, None if switch is None else str(switch), bool(data.get("toggle", False)),
                         bool(data.get("invert", False)), None if event is None else str(event),
                         mapping(data.get("params"), f"{where}: params"))
    return keys
