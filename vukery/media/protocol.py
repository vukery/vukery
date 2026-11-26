"""The vukery media protocol: JSON messages, one per line, over a local socket.

The engine decides what's shown; media controllers only render.

1. A media controller connects and says hello::

       {"type": "hello", "version": 1, "displays": ["main"], "audio": false}

2. The engine answers with everything it needs::

       {"type": "welcome", "version": 1,
        "displays": {"main": {"width": 800, "height": 480}},
        "slides": {"base": {"background": "000000", "widgets": [...]}},
        "showing": {"main": "attract"},
        "player": null, "players": {}}

3. Then, as things change::

       {"type": "show", "display": "main", "slide": "base"}       # the slide now on a display
       {"type": "player", "number": 1, "vars": {"score": 1000}}   # player variables
       {"type": "turn", "number": 2}                               # whose turn it is (null: no game)
       {"type": "bye"}                                             # the engine is stopping

Messages a media controller doesn't recognize must be ignored, so the
protocol can grow without breaking older controllers.
"""

import json
from typing import Any

VERSION = 1
DEFAULT_PORT = 5051


def encode(message: dict[str, Any]) -> bytes:
    return json.dumps(message, separators=(",", ":")).encode() + b"\n"


def decode(line: bytes) -> dict[str, Any]:
    message = json.loads(line)
    if not isinstance(message, dict) or "type" not in message:
        raise ValueError(f"Not a vukery media message: {line[:80]!r}")
    return message  # type: ignore[return-value]
