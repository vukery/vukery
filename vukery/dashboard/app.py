"""The ``vuk me`` dashboard: one full-screen pyglet window showing the whole machine.

Runs as its own process, started by ``vuk me``, and connects to the engine as
a media controller with ``"dashboard": true``. The columns, left to right:

1. switches, lights, coils and other devices;
2. the virtual backbox (the game's displays) over the game and its modes;
3. the virtual playfield.

Click a switch (in its pane or on the playfield) to press it while the mouse
button is down; right-click to lock it on or off. That works on the simulated
platforms only. Nothing here can fire a coil: the protocol has no message for
it. Esc closes the dashboard, and ``vuk me`` stops the game with it.
"""

import asyncio
import math
import sys
from typing import Any, Literal

from vukery.dashboard import layout as lay
from vukery.dashboard.state import DashboardState
from vukery.mc.app import FRAME_SECONDS, connect, draw_slide
from vukery.media import protocol

BACKGROUND = (18, 18, 22)
PANE = (30, 30, 36)
Color = tuple[int, int, int, int]
TEXT: Color = (225, 225, 230, 255)
DIM: Color = (130, 130, 140, 255)
RIGHT_BUTTON = 4  # pyglet.window.mouse.RIGHT
OFF = (60, 60, 70)
SWITCH_ON = (80, 210, 120)
COIL_ON = (245, 95, 60)
PLAYFIELD = (24, 40, 34)


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _light_color(color: str) -> tuple[int, int, int]:
    """Lights that are off still show as a dark disc."""
    rgb = _rgb(color)
    return rgb if any(rgb) else (40, 40, 44)


class DashboardView:
    """Builds the window's shapes once per layout and window size, then updates their colors."""

    def __init__(self, window: Any, state: DashboardState, send: Any):
        self.window = window
        self.state = state
        self.send = send  # send(message) to the engine
        self.built_for: tuple[int, int, int] | None = None
        self.locked: set[str] = set()
        self.pressed: str | None = None

    # --- building

    def build(self) -> None:
        import pyglet

        self.batch = pyglet.graphics.Batch()
        back, front, top = (pyglet.graphics.Group(order=i) for i in range(3))
        self.groups = (back, front, top)
        self.panes = lay.panes(self.window.width, self.window.height)
        self.keep: list[Any] = []  # static shapes and labels: kept alive, never touched again
        self.switch_marks: list[tuple[str, Any]] = []
        self.light_marks: list[tuple[str, Any]] = []
        self.coil_marks: list[tuple[str, Any]] = []
        self.flippers: list[tuple[str, Any, Any]] = []
        self.hits: list[tuple[lay.Rect, str]] = []
        layout = self.state.layout
        can_press = bool(layout.get("switch_input"))
        titles = {
            "switches": "Switches" + ("   click: press · right-click: lock" if can_press else "   from the hardware"),
            "lights": "Lights", "coils": "Coils", "devices": "Devices",
            "backbox": "Backbox", "game": "Game", "playfield": "Playfield",
        }
        for name, rect in self.panes.items():
            self.keep.append(pyglet.shapes.Rectangle(rect.x, rect.y, rect.w, rect.h, color=PANE,
                                                     batch=self.batch, group=back))
            self.keep.append(self._label(titles[name], rect.x + 8, rect.y + rect.h - 8, 13, DIM, anchor_y="top"))

        self._list("switches", [s["name"] for s in layout.get("switches", [])], self.switch_marks, square=True)
        self._list("lights", [light["name"] for light in layout.get("lights", [])], self.light_marks)
        self._list("coils", [c["name"] for c in layout.get("coils", [])], self.coil_marks, square=True)
        for (name, _), cell in zip(self.switch_marks, lay.cells(self.panes["switches"],
                                                                 len(self.switch_marks)), strict=True):
            self.hits.append((cell, name))

        devices = self.panes["devices"]
        self.devices_label = self._label("", devices.x + 10, devices.y + devices.h - 38, 13, TEXT,
                                         anchor_y="top", width=devices.w - 20)
        game = self.panes["game"]
        self.game_label = self._label("", game.x + 10, game.y + game.h - 38, 15, TEXT,
                                      anchor_y="top", width=game.w - 20)
        self._build_playfield()
        self.built_for = (self.state.layout_version, self.window.width, self.window.height)

    def _label(self, text: str, x: float, y: float, size: int, color: Color,
               anchor_y: Literal["top", "center"] = "center",
               width: float | None = None) -> Any:
        import pyglet

        return pyglet.text.Label(text, x=int(x), y=int(y), font_size=size, color=color, anchor_y=anchor_y,
                                 width=int(width) if width else None, multiline=width is not None,
                                 batch=self.batch, group=self.groups[2])

    def _list(self, pane: str, names: list[str], marks: list[tuple[str, Any]], square: bool = False) -> None:
        import pyglet

        rect = self.panes[pane]
        if not names:
            self.keep.append(self._label("none", rect.x + 10, rect.y + rect.h - 40, 10, DIM))
        for name, cell in zip(names, lay.cells(rect, len(names)), strict=True):
            size = min(cell.h - 8, 14)
            cy = cell.y + cell.h / 2
            shape = (pyglet.shapes.Rectangle(cell.x, cy - size / 2, size, size, color=OFF,
                                             batch=self.batch, group=self.groups[1]) if square else
                     pyglet.shapes.Circle(cell.x + size / 2, cy, size / 2, color=OFF,
                                          batch=self.batch, group=self.groups[1]))
            marks.append((name, shape))
            self.keep.append(self._label(name, cell.x + size + 8, cy, max(int(cell.h * 0.5), 7), TEXT))

    def _build_playfield(self) -> None:
        import pyglet

        field = self.panes["playfield"].inset(14)
        field = lay.Rect(field.x, field.y, field.w, field.h - 18)  # room for the title
        self.field = field
        self.keep.append(pyglet.shapes.Rectangle(field.x, field.y, field.w, field.h, color=PLAYFIELD,
                                                 batch=self.batch, group=self.groups[0]))
        self.keep.append(pyglet.shapes.Box(field.x, field.y, field.w, field.h, thickness=2, color=(90, 110, 100),
                                           batch=self.batch, group=self.groups[1]))
        length = field.w * 0.17
        for name, (fx, fy, direction) in lay.flipper_spots(self.state.layout).items():
            x, y = field.at(fx, fy)
            rest = (x + direction * length * math.cos(0.45), y - length * math.sin(0.45))
            up = (x + direction * length * math.cos(0.35), y + length * math.sin(0.35))
            down_line = pyglet.shapes.Line(x, y, *rest, thickness=7, color=OFF, batch=self.batch, group=self.groups[1])
            up_line = pyglet.shapes.Line(x, y, *up, thickness=7, color=COIL_ON, batch=self.batch, group=self.groups[1])
            coil = next(f["coil"] for f in self.state.layout["flippers"] if f["name"] == name)
            self.flippers.append((coil, down_line, up_line))
        switches = {s["name"] for s in self.state.layout.get("switches", [])}
        radius = max(field.w * 0.022, 5)
        for name, (fx, fy) in lay.playfield_spots(self.state.layout).items():
            x, y = field.at(fx, fy)
            if name in switches:
                shape = pyglet.shapes.Rectangle(x - radius, y - radius, radius * 2, radius * 2, color=OFF,
                                                batch=self.batch, group=self.groups[1])
                self.switch_marks.append((name, shape))
                self.hits.append((lay.Rect(x - radius * 1.5, y - radius * 1.5, radius * 3, radius * 3), name))
            else:
                shape = pyglet.shapes.Circle(x, y, radius, color=OFF, batch=self.batch, group=self.groups[1])
                self.light_marks.append((name, shape))
            self.keep.append(pyglet.text.Label(name, x=int(x), y=int(y - radius - 3), font_size=9, color=DIM,
                                               anchor_x="center", anchor_y="top", batch=self.batch,
                                               group=self.groups[2]))

    # --- drawing

    def draw(self) -> None:
        import pyglet

        if self.built_for != (self.state.layout_version, self.window.width, self.window.height):
            self.build()
        state = self.state
        for name, shape in self.switch_marks:
            shape.color = SWITCH_ON if state.switch(name) else OFF
        for name, shape in self.light_marks:
            shape.color = _light_color(state.light(name))
        for name, shape in self.coil_marks:
            shape.color = COIL_ON if state.coil_on(name) else OFF
        for coil, down_line, up_line in self.flippers:
            up = state.coil_on(coil)
            down_line.visible, up_line.visible = not up, up
        devices = "\n".join(state.device_lines()) or "none"
        if self.devices_label.text != devices:
            self.devices_label.text = devices
        game = "\n".join(state.game_lines() if state.connected else ["waiting for the engine…"])
        if self.game_label.text != game:
            self.game_label.text = game

        self.window.switch_to()
        pyglet.gl.glClearColor(BACKGROUND[0] / 255, BACKGROUND[1] / 255, BACKGROUND[2] / 255, 1)
        self.window.clear()
        self.batch.draw()
        sizes = [(name, int(d.get("width", 800)), int(d.get("height", 480))) for name, d in state.displays.items()]
        box = self.panes["backbox"]
        box = lay.Rect(box.x, box.y, box.w, box.h - 22)
        if not sizes:
            pyglet.text.Label("no displays", x=int(box.x + box.w / 2), y=int(box.y + box.h / 2), font_size=11,
                              color=DIM, anchor_x="center", anchor_y="center").draw()
        for name, rect in lay.displays(box, sizes).items():
            draw_slide(state, name, rect.x, rect.y, rect.w, rect.h)

    # --- input

    def switch_at(self, x: float, y: float) -> str | None:
        return next((name for rect, name in self.hits if rect.contains(x, y)), None)

    def press(self, x: float, y: float, right: bool) -> None:
        name = self.switch_at(x, y)
        if name is None or not self.state.layout.get("switch_input"):
            return
        if right:
            if name in self.locked:
                self.locked.discard(name)
                self.send({"type": "switch", "name": name, "state": 0})
            else:
                self.locked.add(name)
                self.send({"type": "switch", "name": name, "state": 1})
        elif name not in self.locked:
            self.pressed = name
            self.send({"type": "switch", "name": name, "state": 1})

    def release(self) -> None:
        if self.pressed is not None:
            self.send({"type": "switch", "name": self.pressed, "state": 0})
            self.pressed = None


def run(port: int, windowed: tuple[int, int] | None = None) -> int:
    """Open the dashboard (full screen, or ``windowed`` at a size) until it's closed or the engine stops."""
    import pyglet

    state = DashboardState()
    link: dict[str, Any] = {}
    window = (pyglet.window.Window(*windowed, caption="vukery: vuk me") if windowed else
              pyglet.window.Window(fullscreen=True, caption="vukery: vuk me"))

    def send(message: dict[str, Any]) -> None:
        if writer := link.get("writer"):
            writer.write(protocol.encode(message))

    view = DashboardView(window, state, send)

    def on_mouse_press(x: int, y: int, button: int, modifiers: int) -> None:
        view.press(x, y, right=button == RIGHT_BUTTON)

    def on_mouse_release(x: int, y: int, button: int, modifiers: int) -> None:
        view.release()

    window.push_handlers(on_mouse_press=on_mouse_press, on_mouse_release=on_mouse_release)

    async def frames() -> None:
        while not state.engine_stopped and not window.has_exit:
            pyglet.clock.tick()
            window.dispatch_events()
            view.draw()
            window.flip()
            await asyncio.sleep(FRAME_SECONDS)

    async def main() -> None:
        connection = asyncio.create_task(connect(state, port, [], audio=False, dashboard=True, link=link))
        try:
            await frames()
        finally:
            connection.cancel()
            window.close()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    return 0


def main(argv: list[str]) -> int:
    """``python -m vukery.dashboard PORT [WIDTHxHEIGHT]``: vuk me starts it this way."""
    port = int(argv[0]) if argv else protocol.DEFAULT_PORT
    windowed = tuple(int(n) for n in argv[1].split("x")) if len(argv) > 1 else None
    return run(port, (windowed[0], windowed[1]) if windowed else None)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
