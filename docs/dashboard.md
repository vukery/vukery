# The dashboard: `vuk me`

`vuk me` runs your game on your computer with a dashboard that shows the
whole machine, and lets you play it by clicking switches.

```console
cd my_machine
uv run vuk me       # Esc closes the dashboard and stops the game
```

It opens as a 1280×800 window (twice that many pixels on a Retina display)
that you can resize or make full screen. `vuk us` is how a machine runs:
the game and its displays full screen, with no dashboard. See
[The vuk command](cli.md).

## What's on it

| Pane | What it shows |
|---|---|
| **List** (left, full height) | **Game**: whose turn it is, the ball, every player's score, and the running modes with their priorities. Then every **switch** (green while active), **light** (in its current color), **coil** (orange while held, or for a moment after a pulse) and **device** (balls in each trough; whether each flipper and autofire coil is enabled). Text stays one size: scroll with the wheel or the scrollbar. |
| **Backbox** | A virtual backbox, with any switches and lights you've placed in it |
| **One pane per display** | What each of the game's displays shows, drawn just as `vuk us` draws it, keeping the display's shape |
| **Playfield** | A virtual playfield with the switches and lights you've placed on it, and the flippers, which flip up while their coil is on |

The backbox and playfield are drawn on wood backgrounds that come with
vukery, and keep their shape however their panes are sized: the backbox is
square and the playfield is twice as tall as it's wide, as large as fits.
Point at a switch or light on them to see its name.

## Playing with switches

- **Click a switch**, in the list, the backbox or on the playfield, to press
  it. A quick click taps it; holding the button holds it.
- **Right-click to lock it on** (a ball sitting in a trough or a hole);
  right-click again to release it.

Switches can only be pressed on the simulated platforms (`development` and
`test`). With `--hardware`, the dashboard just shows what the real switches
do.

**The dashboard can never fire a coil.** Coils fire only from the game
running in the engine; the dashboard has no way to ask for one.

## Placing switches and lights

**Drag a switch or light from the list** into the backbox or onto the
playfield, and drop it where it is on your machine:
- **To move it,** drag it again.
- **To take it off,** drag it back to the list.
- **Only placed switches and lights appear** in those panes. The list
  shows each one's place.

Positions are saved as fractions of the pane, from its bottom-left corner,
so they move and scale with it when you resize the pane:

```yaml
dashboard:
  backbox:
    l_shoot_again: [0.5, 0.2]
  playfield:
    s_target: [0.5, 0.62]   # [x, y], each from 0 to 1
    l_frenzy: [0.5, 0.54]
```

A switch or light can be in the backbox or on the playfield, not both, and
the names have to be switches or lights in the machine config.

## Resizing the panes

**Drag the edge between two panes** to resize them: the list's edge, the
playfield's edge, and the edges between the backbox and each display. No
pane gets smaller than 5% of the window.

## `config/dashboard.yaml`

Whenever you resize a pane or place something, `vuk me` saves the layout to
`config/dashboard.yaml`. Pane sizes are a percentage of the window, to the
nearest tenth:

```yaml
# vuk me's dashboard. vuk me rewrites this file when you resize a pane or drag
# a switch or light into place, unless arrangement_lock is true. Hand edits are
# fine, too.

dashboard:
  arrangement_lock: false  # true: vuk me can't change the layout
  panes:  # each pane's width and height, as a % of the window
    list:      {width: 40.0, height: 100.0}
    backbox:   {width: 35.0, height: 55.0}
    main:      {width: 35.0, height: 22.5}
    apron:     {width: 35.0, height: 22.5}
    playfield: {width: 25.0, height: 100.0}
  playfield:  # switches and lights placed in the playfield: [x, y], each 0 to 1
    s_target: [0.5, 0.62]
```

- **Set `arrangement_lock: true`** once the layout is right. Then panes
  can't be resized, and nothing can be placed or moved.
- **Each display has a pane named after it** (`main` and `apron` above).
- **If you edit sizes by hand, they have to fit together:**
  - the list and playfield are full height;
  - the backbox and display panes share the middle column's width, and
    their heights add up to 100;
  - the widths across add up to 100.

  vukery says which pane doesn't fit.
- **Panes left out keep their default size.** Without the file, the list is
  40%, the playfield 25%, and the backbox gets 55% of the middle column.
- **The file is for `vuk me` only.** `vuk it` creates it, and it's the
  `dashboard:` section of the config, merged like any other config file.

## Status (0.0.x)

Works: everything above, on the simulated platforms. Planned:
- your own backbox and playfield artwork;
- trying it against real hardware (FAST Nano) with `--hardware`.

## Coming from MPF

| MPF | vukery |
|---|---|
| `mpf both` plus `mpf monitor` | `vuk me` |
| MPF Monitor's `monitor.yaml` positions | `dashboard: playfield:` and `backbox:` in `config/dashboard.yaml` |
| dragging a device onto the playfield image in MPF Monitor | dragging it from the list onto the playfield or backbox |
| clicking a switch in MPF Monitor | clicking it on the dashboard (right-click locks it) |
