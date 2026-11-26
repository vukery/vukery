# The dashboard: `vuk me`

`vuk me` runs your game on your computer with a full-screen dashboard that
shows the whole machine, and lets you play it by clicking switches.

```console
cd my_game
uv run vuk me       # Esc closes the dashboard and stops the game
```

`vuk us` is how a machine runs: the game, plus the displays full screen, and
no dashboard. See [The vuk command](cli.md).

## What's on it

The dashboard has three columns:

| Column | What it shows |
|---|---|
| **1. Devices** | Four panes: **switches** (green while active), **lights** (in their current color), **coils** (orange while held, or for a moment after a pulse), and **devices**: balls in each trough, and whether each flipper and autofire coil is enabled |
| **2. Backbox and game** | Top: a **virtual backbox** with the game's displays in it, stacked in config order and drawn just as `vuk us` draws them. Bottom: the **game**: whose turn it is, the ball, every player's score, and the running modes with their priorities |
| **3. Playfield** | A **virtual playfield** with its switches (squares), lights (circles) and flippers, which flip up while their coil is on |

## Playing with switches

- **Click a switch,** in the switches pane or on the playfield, to press
  it. It stays active while the mouse button is down.
- **Right-click to lock it on** (a ball sitting in a trough or a hole);
  right-click again to release it.

Switches can only be pressed on the simulated platforms (`development`
and `test`). With `--hardware`, the dashboard just shows what the real
switches do.

**The dashboard can never fire a coil.** Coils fire only from the game
running in the engine. The dashboard has no way to ask for one.

## Resizing the panes

Drag the edge between two panes to resize them: the two column edges, the
edge inside each of column 1's rows, column 1's row edge, and the edge
between the backbox and the game. No pane gets smaller than 5% of the
window. Text grows with the window.

When you let go, `vuk me` saves every pane's size to
`config/dashboard.yaml`, as a percentage of the window to the nearest
tenth:

```yaml
# vuk me's dashboard. vuk me rewrites this file when you drag the edge of a pane,
# unless arrangement_lock is true. Hand edits are fine, too.

dashboard:
  arrangement_lock: false  # true: the panes can't be resized from vuk me
  panes:  # each pane's width and height, as a % of the window
    switches:  {width: 21.9, height: 50.0}
    lights:    {width: 21.9, height: 50.0}
    coils:     {width: 21.9, height: 50.0}
    devices:   {width: 21.9, height: 50.0}
    backbox:   {width: 28.1, height: 50.0}
    game:      {width: 28.1, height: 50.0}
    playfield: {width: 28.1, height: 100.0}
  playfield:  # where switches and lights sit on the virtual playfield: [x, y], each 0 to 1
    s_target: [0.5, 0.62]
```

- **Set `arrangement_lock: true`** once the layout is right, and the edges
  stay put.
- **If you edit the sizes by hand, they have to fit together:** panes in a
  row share its height, column 1's two rows are equally wide, and the widths
  across add up to 100. vukery says which pane doesn't fit.
- **Panes left out keep their default size.** Without the file, everything
  is at the defaults shown above.
- **The file is for `vuk me` only.** `vuk it` creates it, and it's the
  `dashboard:` section of the config, merged like any other config file.

## Placing things on the playfield

Without any config, the playfield is laid out for you:
- ball device switches sit in a row at the bottom;
- autofire switches (slingshots, pop bumpers) sit on their side, from
  `left` or `right` in their name;
- cabinet switches (start, flipper buttons, tilt, coin door…) stay off the
  playfield, in the switches pane only;
- everything else goes in a grid at the top.

To put a switch or light where it really is, give its position under
`playfield:` in `config/dashboard.yaml`, from the playfield's bottom-left
corner:

```yaml
dashboard:
  playfield:
    s_target: [0.5, 0.62] # [x, y], each from 0 to 1
    l_frenzy: [0.5, 0.54]
```

The names must be switches or lights in the config. This section describes
the machine, so it's YAML.

## Status (0.0.x)

Works: everything above, on the simulated platforms. The backbox and
playfield are drawn on wood backgrounds that come with vukery. Planned:
- dragging things on the playfield and saving their positions;
- your own backbox and playfield artwork;
- trying it against real hardware (FAST Nano) with `--hardware`.

## Coming from MPF

| MPF | vukery |
|---|---|
| `mpf both` plus `mpf monitor` | `vuk me` |
| MPF Monitor's `monitor.yaml` positions | `dashboard: playfield:` in `config/dashboard.yaml` |
| clicking a switch in MPF Monitor | clicking it on the dashboard (right-click locks it) |
