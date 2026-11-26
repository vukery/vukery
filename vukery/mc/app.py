"""The default media controller: pyglet windows, one per display, fed by the engine.

Runs as its own process (``vuk mc``), started by ``vuk it``. It connects to
the engine, retrying until the engine is up, and draws what ``MediaState``
says. Each display is full screen on its own monitor (``screen:`` in its
``displays:`` entry, or the next one in order). pyglet is only imported
here and in the dashboard, so the engine never needs it.
"""

import asyncio
import sys
from typing import Any, cast

from vukery.core.log import get_logger
from vukery.mc.state import MediaState
from vukery.media import protocol

log = get_logger("mc")
FRAME_SECONDS = 1 / 60


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def draw_slide(state: MediaState, display: str, x: float, y: float, width: float, height: float) -> None:
    """Draw ``display``'s current slide into a rect, in window units.

    The display windows use the whole window; the vuk me dashboard draws into
    its virtual backbox.
    """
    import pyglet

    pyglet.shapes.Rectangle(x, y, width, height, color=_rgb(state.background(display))).draw()
    if not state.connected:
        pyglet.text.Label("waiting for the engine…", font_size=max(int(height * 0.04), 8), x=int(x + width / 2),
                          y=int(y + height / 2), anchor_x="center", anchor_y="center").draw()
        return
    for text in state.texts(display):
        pyglet.text.Label(text.text, font_size=max(int(text.size * height * 0.75), 1),
                          x=int(x + text.x * width), y=int(y + text.y * height),
                          anchor_x=cast(Any, text.anchor), anchor_y="center",
                          color=(*_rgb(text.color), 255)).draw()


def draw(window: Any, state: MediaState, display: str) -> None:
    """Draw ``display``'s current slide filling ``window``.

    pyglet's own resize handling sets the viewport and projection (including on
    HiDPI screens), as long as the window's events are dispatched before drawing.
    """
    window.switch_to()
    window.clear()
    draw_slide(state, display, 0, 0, window.width, window.height)


async def connect(state: MediaState, port: int, displays: list[str], audio: bool,
                  dashboard: bool = False, link: dict[str, Any] | None = None) -> None:
    """Stay connected to the engine, reconnecting if it restarts.

    ``link["writer"]`` is the open connection while there is one (the dashboard
    sends switch changes through it).
    """
    while not state.engine_stopped:
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.5)
            continue
        hello: dict[str, Any] = {"type": "hello", "version": protocol.VERSION, "displays": displays, "audio": audio}
        if dashboard:
            hello["dashboard"] = True
        writer.write(protocol.encode(hello))
        if link is not None:
            link["writer"] = writer
        log.info("Connected to the engine on port %s", port)
        while line := await reader.readline():
            state.apply(protocol.decode(line))
        state.connected = False
        if link is not None:
            link.pop("writer", None)
        writer.close()
        log.info("Disconnected from the engine")


def run(port: int, display_configs: dict[str, dict[str, Any]], only: str | None = None,
        windowed: bool = False) -> int:
    """Open a full-screen window for each display (or just ``only``) and draw until the engine stops.

    ``windowed`` opens them at their configured size instead (``vuk mc --windowed``).
    """
    import pyglet  # imported here so nothing else needs pyglet

    names = [only] if only else list(display_configs)
    state = MediaState()
    windows: dict[str, Any] = {}
    screens = pyglet.display.get_display().get_screens()
    for name in names:
        size = display_configs[name]
        if windowed:
            window = pyglet.window.Window(int(size.get("width", 800)), int(size.get("height", 480)),
                                          caption=f"vukery: {name}")
        else:
            index = int(size.get("screen", list(display_configs).index(name)))
            window = pyglet.window.Window(fullscreen=True, screen=screens[min(index, len(screens) - 1)],
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
