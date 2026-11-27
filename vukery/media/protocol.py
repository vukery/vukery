"""The vukery media protocol: JSON messages, one per line, over a local socket.

The engine decides what's shown; media controllers only render.

1. A media controller connects and says hello::

       {"type": "hello", "version": 2, "displays": ["main"], "audio": false}

2. The engine answers with everything it needs::

       {"type": "welcome", "version": 2,
        "displays": {"main": {"width": 800, "height": 480}},
        "scenes": {"score": {"type": "scene", "background": "000000", "actors": [...]}},
        "showing": {"main": "attract"},
        "player": null, "players": {}}

3. Then, as things change::

       {"type": "show", "display": "main", "scene": "score"}      # the scene now on a display
       {"type": "player", "number": 1, "vars": {"score": 1000}}   # player variables
       {"type": "turn", "number": 2}                               # whose turn it is (null: no game)
       {"type": "values", "mode": "high_score", "values": {"initials": "AB"}}  # for scenes: {high_score.initials}
       {"type": "bye"}                                             # the engine is stopping

Messages a media controller doesn't recognize must be ignored, so the
protocol can grow without breaking older controllers.
"""

import json
from typing import Any

VERSION = 2  # 2: slides became scenes (vukery.media.scenes)
DEFAULT_PORT = 5051


def encode(message: dict[str, Any]) -> bytes:
    return json.dumps(message, separators=(",", ":")).encode() + b"\n"


def decode(line: bytes) -> dict[str, Any]:
    message = json.loads(line)
    if not isinstance(message, dict) or "type" not in message:
        raise ValueError(f"Not a vukery media message: {line[:80]!r}")
    return message  # type: ignore[return-value]
