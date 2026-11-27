"""The ``vuk me`` dashboard: one pyglet window showing the whole machine.

Runs as its own process, started by ``vuk me``, and connects to the engine as
a media controller with ``"dashboard": true``. It opens as a 1280×800 window
(doubled on a Retina display) that you can resize. The panes, left to right:

1. the list: the game and its modes, then every switch, light, coil and
   device. Scroll it with the wheel or its scrollbar;
2. the backbox, over a pane for each of the game's displays;
3. the playfield.

- **Click a switch** (in the list, the backbox or on the playfield) to press
  it: a quick click taps it, holding the button holds it. Right-click locks
  it on, or off again. That works on the simulated platforms only.
- **Drag a switch or light** from the list into the backbox or onto the
  playfield to place it there, or drag a placed one to move it. Drag it
  back to the list to take it off. Positions are fractions of the pane, so
  they move and scale with it.
- **Drag the edge between two panes** to resize them.

Layout changes are saved to ``config/dashboard.yaml``, unless
``arrangement_lock: true``. Nothing here can fire a coil: the protocol has
no message for it. Esc closes the dashboard, and ``vuk me`` stops the game
with it.
"""

import asyncio
import math
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vukery.core.log import get_logger
from vukery.dashboard import layout as lay
from vukery.dashboard.keys import KeyboardInput, key_name
from vukery.dashboard.state import DashboardState
from vukery.mc.app import FRAME_SECONDS, connect, draw_scene, pixel_ratio
from vukery.media import protocol
from vukery.media.arrangement import PLACES, Arrangement, write_config

log = get_logger("dashboard")
ASSETS = Path(__file__).parents[1] / "assets"
WINDOW = (1280, 800)    # in points: pyglet doubles it on a Retina display

Color = tuple[int, int, int, int]
BACKGROUND = (18, 18, 22)
PANE = (30, 30, 36)
TEXT: Color = (225, 225, 230, 255)
DIM: Color = (130, 130, 140, 255)
WHITE: Color = (255, 255, 255, 255)
OFF = (60, 60, 70)
SWITCH_ON = (80, 210, 120)
COIL_ON = (245, 95, 60)
DROP = (255, 205, 60)

FONT = 18               # the list's text, in points; it never resizes: the list scrolls instead
SMALL = 14              # the list's hints and place tags
TITLE = 20              # the list's section titles
PANE_TITLE = 13         # the other panes' titles
LABEL = 11              # names shown on the backbox and playfield
LINE = 30               # line height of the game and devices text
SCROLLBAR = 10
SPOT = 7                # radius of a placed switch or light
HOLD = 0.15             # seconds a press waits, to tell a click from a drag
TAP = 0.08              # how long a quick click holds a switch
DRAG_START = 6          # how far (in window units) the pointer moves before a press becomes a drag
RIGHT_BUTTON = 4        # pyglet.window.mouse.RIGHT
FIXED_PANES = ("list", "backbox", "playfield")
SHAPES = {"backbox": (1, 1), "playfield": (1, 2)}  # width : height, kept however the panes are sized


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _light_color(color: str) -> tuple[int, int, int]:
    """Lights that are off still show as a dark disc."""
    rgb = _rgb(color)
    return rgb if any(rgb) else (40, 40, 44)


@dataclass
class _Pending:
    """A left press on a switch or light, until it's clearly a click or a drag."""

    name: str
    kind: str
    x: float
    y: float
    since: float
    pressed: bool = False   # the switch press has gone to the engine


@dataclass
class _Carried:
    """A switch or light being dragged to a new place."""

    name: str
    x: float
    y: float


def _scroll_group(view: DashboardView, order: int) -> Any:
    """A group that clips to the list and moves it by the scroll amount."""
    import pyglet
    from pyglet import gl
    from pyglet.math import Mat4, Vec3

    class ScrollGroup(pyglet.graphics.Group):
        def __init__(self) -> None:
            super().__init__(order=order)
            self.saved: Any = None

        def __eq__(self, other: object) -> bool:  # pyglet merges equal groups; this one is unique
            return self is other

        def __hash__(self) -> int:
            return id(self)

        def set_state(self) -> None:
            area, ratio = view.list_area, pixel_ratio(view.window)
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(int(area.x * ratio), int(area.y * ratio), int(area.w * ratio), int(area.h * ratio))
            self.saved = view.window.view
            view.window.view = self.saved @ Mat4.from_translation(Vec3(0, view.scroll, 0))

        def unset_state(self) -> None:
            gl.glDisable(gl.GL_SCISSOR_TEST)
            view.window.view = self.saved

    return ScrollGroup()


class DashboardView:
    """Builds the window's shapes once per layout, then updates colors and text each frame."""

    def __init__(self, window: Any, state: DashboardState, send: Callable[[dict[str, Any]], None],
                 now: Callable[[], float] = time.monotonic):
        self.window = window
        self.state = state
        self.send = send          # send(message) to the engine
        self.now = now
        self.built_for: tuple[Any, ...] | None = None
        self.layout_version = 0
        self.arrangement = Arrangement()
        self.positions: dict[str, dict[str, list[float]]] = {place: {} for place in PLACES}
        self.placed_version = 0
        self.scroll = 0.0
        self.scrolling = False
        self.list_total = 0.0
        self.list_area = lay.Rect(0, 0, 0, 0)
        self.track = lay.Rect(0, 0, 0, 0)
        self.panes: dict[str, lay.Rect] = {}
        self.dragging: lay.Edge | None = None
        self.pending: _Pending | None = None
        self.carried: _Carried | None = None
        self.locked: set[str] = set()
        self.releases: list[tuple[float, str]] = []   # (when, switch) for quick clicks
        self.list_hits: list[tuple[lay.Rect, str, str]] = []   # (rect before scrolling, name, kind)
        self.spot_hits: list[tuple[lay.Rect, str, str]] = []   # (rect, name, kind) in the backbox and playfield
        self.hover: tuple[str, float, float] | None = None
        self.images: dict[str, Any] = {}
        self.take_layout()

    # --- the layout

    def take_layout(self) -> None:
        """Take the configured sizes and places from the engine's welcome, and lay out the panes."""
        self.layout_version = self.state.layout_version
        layout = self.state.layout
        panes = layout.get("panes", {})
        displays = [name for name in panes if name not in FIXED_PANES]
        self.arrangement = Arrangement.from_panes(panes, displays)
        self.positions = {place: dict(layout.get("positions", {}).get(place, {})) for place in PLACES}
        self.layout_panes()

    def layout_panes(self) -> None:
        """Where the panes, the list and its scrollbar are, for the current window size and arrangement."""
        self.panes = lay.panes(self.window.width, self.window.height, self.arrangement)
        pane = self.panes["list"]
        self.list_area = lay.Rect(pane.x, pane.y + 4, pane.w - SCROLLBAR - 6, pane.h - 8)
        self.track = lay.Rect(pane.x + pane.w - SCROLLBAR - 3, pane.y + 6, SCROLLBAR, pane.h - 12)
        rows, self.list_total = lay.list_rows(self.state.layout, LINE)
        self.scroll = min(self.scroll, lay.scroll_limit(self.list_total, self.list_area.h))
        top = self.list_area.y + self.list_area.h
        width = self.list_area.w / lay.COLUMNS
        self.list_hits = [(lay.Rect(self.list_area.x + row.column * width, top - row.top - row.height, width,
                                    row.height), row.name, row.kind)
                          for row in rows if row.kind in ("switch", "light")]
        switches = {s["name"] for s in self.state.layout.get("switches", [])}
        self.spot_hits = []
        for place in PLACES:
            area = self.area(place)
            for name, (fx, fy) in self.positions[place].items():
                x, y = area.at(fx, fy)
                self.spot_hits.append((lay.Rect(x - SPOT - 3, y - SPOT - 3, SPOT * 2 + 6, SPOT * 2 + 6), name,
                                       "switch" if name in switches else "light"))

    def area(self, place: str) -> lay.Rect:
        """The backbox (square) or playfield (1:2), as large as fits in its pane below the title.

        Placed switches and lights are fractions of this area, so they stay put
        however the window or the panes are resized.
        """
        width, height = SHAPES[place]
        return lay.fit(lay.content(self.panes[place]), width, height)

    def _key(self) -> tuple[Any, ...]:
        return (self.state.layout_version, self.window.width, self.window.height, self.arrangement,
                self.placed_version)

    # --- building shapes

    def _image(self, name: str) -> Any:
        import pyglet
        from pyglet.image.codecs import ImageDecodeException

        file = str(self.state.layout.get("artwork", {}).get(name, {}).get("file") or ASSETS / f"{name}.jpg")
        if file not in self.images:
            try:
                self.images[file] = pyglet.image.load(file)
            except (OSError, ImageDecodeException):   # a picture it can't read: draw vukery's, and say so
                log.warning("Can't load %s; drawing vukery's %s instead", file, name)
                self.images[file] = pyglet.image.load(str(ASSETS / f"{name}.jpg"))
        return self.images[file]

    def build(self) -> None:
        import pyglet

        if self.layout_version != self.state.layout_version:
            self.take_layout()
        else:
            self.layout_panes()
        self.batch = pyglet.graphics.Batch()
        self.groups = tuple(pyglet.graphics.Group(order=i) for i in range(4))  # panes, backgrounds, marks, text
        scroll = _scroll_group(self, 5)
        self.list_groups = (pyglet.graphics.Group(order=0, parent=scroll),
                            pyglet.graphics.Group(order=1, parent=scroll))
        self.keep: list[Any] = []
        self.marks: list[tuple[str, str, Any]] = []   # (name, kind, shape): recolored every frame
        self.flippers: list[tuple[str, Any]] = []
        for name, rect in self.panes.items():
            self.keep.append(pyglet.shapes.Rectangle(rect.x, rect.y, rect.w, rect.h, color=PANE,
                                                     batch=self.batch, group=self.groups[0]))
            if name != "list":
                title = name.capitalize() if name in PLACES else f"Display: {name}"
                self.keep.append(self._label(title, rect.x + 10, rect.y + rect.h - 8, PANE_TITLE, DIM,
                                             anchor_y="top"))
        self._build_list()
        for place in PLACES:
            self._build_place(place)
        self.built_for = self._key()

    def _label(self, text: str, x: float, y: float, size: int, color: Color,
               anchor_y: Literal["top", "center", "bottom"] = "center", width: float | None = None,
               group: Any = None, bold: bool = False) -> Any:
        import pyglet

        return pyglet.text.Label(text, x=int(x), y=int(y), font_size=size, color=color, anchor_y=anchor_y,
                                 width=int(width) if width else None, multiline=width is not None, weight=
                                 "bold" if bold else "normal", batch=self.batch, group=group or self.groups[3])

    def _build_list(self) -> None:
        import pyglet

        rows, _ = lay.list_rows(self.state.layout, LINE)
        marks_group, text_group = self.list_groups
        top = self.list_area.y + self.list_area.h
        column_width = self.list_area.w / lay.COLUMNS
        place_of = {name: place for place in PLACES for name in self.positions[place]}
        self.game_labels: list[Any] = []
        self.devices_labels: list[Any] = []
        hints = {"Switches": ("click: press · right-click: lock" if self.state.layout.get("switch_input")
                              else "from the hardware") + (" · drag to place" if self.can_change() else ""),
                 "Lights": "drag to place" if self.can_change() else ""}
        for row in rows:
            y = top - row.top - row.height  # the row's bottom, before scrolling
            x = self.list_area.x + 10 + row.column * column_width
            match row.kind:
                case "title":
                    self.keep.append(self._label(row.name, x - 4, y + 10, TITLE, TEXT, anchor_y="bottom",
                                                 group=text_group, bold=True))
                    if hint := hints.get(row.name):
                        self.keep.append(self._label(hint, x + TITLE * 6, y + 12, SMALL, DIM, anchor_y="bottom",
                                                     group=text_group))
                case "switch" | "light" | "coil":
                    cy, size = y + row.height / 2, 18
                    shape = (pyglet.shapes.Circle(x + size / 2, cy, size / 2, color=OFF, batch=self.batch,
                                                  group=marks_group) if row.kind == "light" else
                             pyglet.shapes.Rectangle(x, cy - size / 2, size, size, color=OFF, batch=self.batch,
                                                     group=marks_group))
                    self.marks.append((row.name, row.kind, shape))
                    tag = {"backbox": "bb", "playfield": "pf"}.get(place_of.get(row.name, ""), "")
                    room = column_width - size - 24 - (SMALL * 2.4 if tag else 0)
                    self._fitted_label(row.name, x + size + 10, cy, room, text_group)
                    if tag:  # where it's placed: bb (backbox) or pf (playfield)
                        self.keep.append(self._label(tag, x + column_width - SMALL * 2.6, cy, SMALL, DIM,
                                                     group=text_group))
                case "game":
                    self.game_labels.append(self._label("", x, y + row.height, FONT, TEXT, anchor_y="top",
                                                        width=column_width - 20, group=text_group))
                case "devices":
                    self.devices_labels.append(self._label("", x, y + row.height, FONT, TEXT, anchor_y="top",
                                                           width=column_width - 20, group=text_group))
                case _:
                    pass

    def _fitted_label(self, text: str, x: float, y: float, room: float, group: Any) -> None:
        """A list name, shortened with … if it's wider than its column."""
        label = self._label(text, x, y, FONT, TEXT, group=group)
        if label.content_width > room:
            short = text
            while short and label.content_width > room:
                short = short[:-1]
                label.text = short + "…"
        self.keep.append(label)

    def _build_place(self, place: str) -> None:
        import pyglet

        area = self.area(place)
        image = self._image(place)
        sprite = pyglet.sprite.Sprite(image, x=area.x, y=area.y, batch=self.batch, group=self.groups[1])
        sprite.scale_x, sprite.scale_y = area.w / image.width, area.h / image.height
        self.keep.append(sprite)
        own_art = self.state.layout.get("artwork", {}).get(place, {}).get("own", False)
        if place == "playfield" and not own_art:  # vukery's art shows the flippers at rest; this is drawn while on
            length = area.w * lay.FLIPPER_LENGTH
            for name, (fx, fy, direction) in lay.flipper_spots(self.state.layout).items():
                x, y = area.at(fx, fy)
                up = (x + direction * length * math.cos(lay.FLIPPER_UP), y + length * math.sin(lay.FLIPPER_UP))
                up_line = pyglet.shapes.Line(x, y, *up, thickness=8, color=COIL_ON, batch=self.batch,
                                             group=self.groups[2])
                coil = next(f["coil"] for f in self.state.layout["flippers"] if f["name"] == name)
                self.flippers.append((coil, up_line))
        for rect, name, kind in self.spot_hits:
            if not area.contains(rect.x + rect.w / 2, rect.y + rect.h / 2) or name not in self.positions[place]:
                continue
            x, y = rect.x + rect.w / 2, rect.y + rect.h / 2
            shape = (pyglet.shapes.Rectangle(x - SPOT, y - SPOT, SPOT * 2, SPOT * 2, color=OFF, batch=self.batch,
                                             group=self.groups[2]) if kind == "switch" else
                     pyglet.shapes.Circle(x, y, SPOT, color=OFF, batch=self.batch, group=self.groups[2]))
            self.marks.append((name, kind, shape))

    # --- drawing

    def draw(self) -> None:
        import pyglet

        if self.built_for != self._key():
            self.build()
        self.tick()
        state = self.state
        for name, kind, shape in self.marks:
            match kind:
                case "switch":
                    shape.color = SWITCH_ON if state.switch(name) else OFF
                case "light":
                    shape.color = _light_color(state.light(name))
                case _:
                    shape.color = COIL_ON if state.coil_on(name) else OFF
        for coil, up_line in self.flippers:
            up_line.visible = state.coil_on(coil)
        waiting: tuple[list[str], list[str]] = (["waiting for the engine…"], [])
        game = state.game_columns() if state.connected else waiting
        devices = state.device_columns()
        for labels, columns in ((self.game_labels, game), (self.devices_labels, devices)):
            for label, lines in zip(labels, columns, strict=True):
                text = "\n".join(lines)
                if label.text != text:
                    label.text = text

        self.window.switch_to()
        pyglet.gl.glClearColor(BACKGROUND[0] / 255, BACKGROUND[1] / 255, BACKGROUND[2] / 255, 1)
        self.window.clear()
        self.batch.draw()
        for name, size in state.displays.items():
            if name in self.panes:
                screen = lay.fit(lay.content(self.panes[name]), int(size.get("width", 800)),
                                 int(size.get("height", 480)))
                draw_scene(state, name, screen.x, screen.y, screen.w, screen.h, pixel_ratio(self.window))
        if self.list_total > self.list_area.h:
            bar = lay.thumb(self.track, self.list_total, self.list_area.h, self.scroll)
            pyglet.shapes.Rectangle(bar.x, bar.y, bar.w, bar.h, color=(90, 90, 100)).draw()
        if self.carried:
            c = self.carried
            pyglet.shapes.Circle(c.x, c.y, SPOT + 2, color=DROP).draw()
            pyglet.text.Label(c.name, x=int(c.x + 14), y=int(c.y), font_size=LABEL, color=WHITE,
                              anchor_y="center").draw()
        elif self.hover:
            name, hx, hy = self.hover
            label = pyglet.text.Label(name, x=int(hx), y=int(hy + SPOT + 6), font_size=LABEL, color=WHITE,
                                      anchor_x="center", anchor_y="bottom")
            pyglet.shapes.Rectangle(label.x - label.content_width / 2 - 4, label.y - 2, label.content_width + 8,
                                    label.content_height + 4, color=(20, 20, 24)).draw()
            label.draw()

    # --- what's under the pointer

    def can_change(self) -> bool:
        return self.state.connected and not self.state.layout.get("arrangement_lock", False)

    def item_at(self, x: float, y: float) -> tuple[str, str] | None:
        """The switch or light (name, kind) under the pointer, in a pane or in the list."""
        for rect, name, kind in self.spot_hits:
            if rect.contains(x, y):
                return name, kind
        if self.list_area.contains(x, y):
            for rect, name, kind in self.list_hits:
                if rect.contains(x, y - self.scroll):
                    return name, kind
        return None

    def edge_at(self, x: float, y: float) -> lay.Edge | None:
        if not self.can_change():
            return None
        return lay.edge_at(self.window.width, self.window.height, self.arrangement, x, y)

    def hover_at(self, x: float, y: float) -> None:
        spot = next(((rect, name) for rect, name, _ in self.spot_hits if rect.contains(x, y)), None)
        self.hover = (spot[1], spot[0].x + spot[0].w / 2, spot[0].y + spot[0].h / 2) if spot else None

    # --- input

    def press(self, x: float, y: float, right: bool = False) -> None:
        item = self.item_at(x, y)
        if right:
            if item and item[1] == "switch" and self.state.layout.get("switch_input"):
                name = item[0]
                if name in self.locked:
                    self.locked.discard(name)
                    self.send({"type": "switch", "name": name, "state": 0})
                else:
                    self.locked.add(name)
                    self.send({"type": "switch", "name": name, "state": 1})
            return
        if edge := self.edge_at(x, y):
            self.dragging = edge
        elif self.track.contains(x, y) and self.list_total > self.list_area.h:
            self.scrolling = True
            self.scroll_to(y)
        elif item:
            self.pending = _Pending(item[0], item[1], x, y, self.now())

    def drag_to(self, x: float, y: float) -> None:
        if self.dragging is not None:
            percent = lay.edge_percent(self.dragging, self.window.width, self.window.height, x, y)
            self.arrangement = self.arrangement.drag(self.dragging.name, percent)
            self.layout_panes()
        elif self.scrolling:
            self.scroll_to(y)
        elif self.carried is not None:
            self.carried.x, self.carried.y = x, y
        elif (p := self.pending) and not p.pressed and self.can_change() \
                and math.hypot(x - p.x, y - p.y) > DRAG_START:
            self.carried = _Carried(p.name, x, y)
            self.pending = None

    def release(self, x: float = 0, y: float = 0) -> None:
        if self.dragging is not None:
            self.dragging = None
            self.save()
        elif self.scrolling:
            self.scrolling = False
        elif self.carried is not None:
            self.drop(self.carried.name, x, y)
            self.carried = None
        elif (p := self.pending) is not None:
            self.pending = None
            if p.kind != "switch" or not self.state.layout.get("switch_input") or p.name in self.locked:
                return
            if p.pressed:
                self.send({"type": "switch", "name": p.name, "state": 0})
            else:  # a quick click: tap the switch
                self.send({"type": "switch", "name": p.name, "state": 1})
                self.releases.append((self.now() + TAP, p.name))

    def tick(self) -> None:
        """Send presses that waited long enough to be holds, and the ends of quick clicks."""
        now = self.now()
        p = self.pending
        if p and not p.pressed and p.kind == "switch" and now - p.since >= HOLD \
                and self.state.layout.get("switch_input") and p.name not in self.locked:
            p.pressed = True
            self.send({"type": "switch", "name": p.name, "state": 1})
        for when, name in [r for r in self.releases if r[0] <= now]:
            self.releases.remove((when, name))
            self.send({"type": "switch", "name": name, "state": 0})

    def scroll_by(self, x: float, y: float, amount: float) -> None:
        if self.list_area.contains(x, y):
            limit = lay.scroll_limit(self.list_total, self.list_area.h)
            self.scroll = min(max(self.scroll - amount * LINE * 2, 0.0), limit)

    def scroll_to(self, y: float) -> None:
        """Put the scrollbar thumb's middle at ``y``."""
        visible, limit = self.list_area.h, lay.scroll_limit(self.list_total, self.list_area.h)
        bar = lay.thumb(self.track, self.list_total, visible, 0)
        free = self.track.h - bar.h
        if free > 0:
            down = (self.track.y + self.track.h - bar.h / 2 - y) / free
            self.scroll = min(max(down * limit, 0.0), limit)

    def drop(self, name: str, x: float, y: float) -> None:
        """Place ``name`` where it was dropped, or take it off if dropped on the list."""
        target = next((place for place in PLACES if lay.content(self.panes[place]).contains(x, y)), None)
        if target is None and not self.panes["list"].contains(x, y):
            return  # dropped somewhere else: nothing changes
        for place in PLACES:
            self.positions[place].pop(name, None)
        if target is not None:
            self.positions[target][name] = list(self.area(target).fraction(x, y))
        self.placed_version += 1
        self.layout_panes()
        self.save()

    def save(self) -> None:
        """Write the panes and places to config/dashboard.yaml."""
        path = self.state.layout.get("config_file")
        if not path:
            return
        try:
            write_config(Path(path), self.arrangement, self.positions)
            log.info("Saved the dashboard layout to %s", path)
        except OSError as e:
            log.warning("Couldn't save the dashboard layout to %s: %s", path, e)


def run(port: int, size: tuple[int, int] = WINDOW) -> int:
    """Open the dashboard window until it's closed or the engine stops. It plays the machine's sounds."""
    import pyglet

    from vukery.mc.audio import Audio

    state = DashboardState(audio=True)
    sound = Audio(state)
    link: dict[str, Any] = {}
    window = pyglet.window.Window(*size, caption="vukery: vuk me", resizable=True)

    def send(message: dict[str, Any]) -> None:
        if writer := link.get("writer"):
            writer.write(protocol.encode(message))

    view = DashboardView(window, state, send)
    cursors = {True: window.get_system_mouse_cursor(window.CURSOR_SIZE_LEFT_RIGHT),
               False: window.get_system_mouse_cursor(window.CURSOR_SIZE_UP_DOWN)}

    def on_mouse_press(x: int, y: int, button: int, modifiers: int) -> None:
        view.press(x, y, right=button == RIGHT_BUTTON)

    def on_mouse_release(x: int, y: int, button: int, modifiers: int) -> None:
        view.release(x, y)

    def on_mouse_drag(x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int) -> None:
        view.drag_to(x, y)

    def on_mouse_motion(x: int, y: int, dx: int, dy: int) -> None:
        edge = view.edge_at(x, y)
        window.set_mouse_cursor(cursors[edge.vertical] if edge else None)
        view.hover_at(x, y)

    def on_mouse_scroll(x: int, y: int, scroll_x: float, scroll_y: float) -> None:
        view.scroll_by(x, y, scroll_y)

    keys = KeyboardInput(state, send)   # the machine's keyboard: section

    def on_key_press(symbol: int, modifiers: int) -> None:
        keys.press(symbol, key_name(symbol, modifiers))

    def on_key_release(symbol: int, modifiers: int) -> None:
        keys.release(symbol)

    window.push_handlers(on_key_press=on_key_press, on_key_release=on_key_release)
    window.push_handlers(on_mouse_press=on_mouse_press, on_mouse_release=on_mouse_release,
                         on_mouse_drag=on_mouse_drag, on_mouse_motion=on_mouse_motion,
                         on_mouse_scroll=on_mouse_scroll)

    async def frames() -> None:
        while not state.engine_stopped and not window.has_exit:
            pyglet.clock.tick()
            sound.frame()
            keys.sync()
            window.dispatch_events()
            view.draw()
            window.flip()
            await asyncio.sleep(FRAME_SECONDS)

    async def main() -> None:
        connection = asyncio.create_task(connect(state, port, [], audio=True, dashboard=True, link=link))
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
    size = tuple(int(n) for n in argv[1].split("x")) if len(argv) > 1 else WINDOW
    return run(port, (size[0], size[1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
