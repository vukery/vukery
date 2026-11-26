"""The default media controller: pyglet windows, one per display, fed by the engine.

Runs as its own process (``vuk mc``), started by ``vuk run``. It connects to
the engine, retrying until the engine is up, and draws what ``MediaState``
says. pyglet is only imported here, so the engine never needs it.
"""

import asyncio
import sys
from typing import Any

from vukery.core.log import get_logger
from vukery.mc.state import MediaState
from vukery.media import protocol

log = get_logger("mc")
FRAME_SECONDS = 1 / 60


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def draw(window: Any, state: MediaState, display: str) -> None:
    """Draw ``display``'s current slide into ``window``, in window units.

    pyglet's own resize handling sets the viewport and projection (including on
    HiDPI screens), as long as the window's events are dispatched before drawing.
    """
    import pyglet

    window.switch_to()
    red, green, blue = _rgb(state.background(display))
    pyglet.gl.glClearColor(red / 255, green / 255, blue / 255, 1)
    window.clear()
    if not state.connected:
        pyglet.text.Label("waiting for the engine…", font_size=14, x=window.width // 2,
                          y=window.height // 2, anchor_x="center", anchor_y="center").draw()
        return
    for text in state.texts(display):
        pyglet.text.Label(text.text, font_size=max(int(text.size * window.height * 0.75), 1),
                          x=int(text.x * window.width), y=int(text.y * window.height),
                          anchor_x=text.anchor, anchor_y="center",
                          color=(*_rgb(text.color), 255)).draw()


async def connect(state: MediaState, port: int, displays: list[str], audio: bool) -> None:
    """Stay connected to the engine, reconnecting if it restarts."""
    while not state.engine_stopped:
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.5)
            continue
        writer.write(protocol.encode({"type": "hello", "version": protocol.VERSION,
                                      "displays": displays, "audio": audio}))
        log.info("Connected to the engine on port %s", port)
        while line := await reader.readline():
            state.apply(protocol.decode(line))
        state.connected = False
        writer.close()
        log.info("Disconnected from the engine")


def run(port: int, display_configs: dict[str, dict[str, Any]], only: str | None = None) -> int:
    """Open a window for each display (or just ``only``) and draw until the engine stops."""
    import pyglet  # imported here so nothing else needs pyglet

    names = [only] if only else list(display_configs)
    state = MediaState()
    windows: dict[str, Any] = {}
    for name in names:
        size = display_configs[name]
        window = pyglet.window.Window(int(size.get("width", 800)), int(size.get("height", 480)),
                                      caption=f"vukery: {name}")
        windows[name] = window

    async def frames() -> None:
        while not state.engine_stopped and all(not w.has_exit for w in windows.values()):
            pyglet.clock.tick()
            for name, window in windows.items():
                window.dispatch_events()
                draw(window, state, name)
                window.flip()
            await asyncio.sleep(FRAME_SECONDS)

    async def main() -> None:
        connection = asyncio.create_task(connect(state, port, names, audio=False))
        try:
            await frames()
        finally:
            connection.cancel()
            for window in windows.values():
                window.close()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(run(protocol.DEFAULT_PORT, {"main": {"width": 800, "height": 480}}))
