# The dashboard: `vuk me`

`vuk me` runs your game on your computer with a full-screen dashboard that
shows the whole machine, and lets you play it by clicking switches.

```console
cd my_game
uv run vuk me       # Esc closes the dashboard and stops the game
```

`vuk it` is how a machine runs: the game, plus the displays full screen, and
no dashboard. See [The vuk command](cli.md).

## What's on it

The dashboard has three columns:

| Column | What it shows |
|---|---|
| **1. Devices** | Four panes: **switches** (green while active), **lights** (in their current color), **coils** (orange while held, or for a moment after a pulse), and **devices**: balls in each trough, and whether each flipper and autofire coil is enabled |
| **2. Backbox and game** | Top: a square **virtual backbox** with the game's displays in it, stacked in config order and drawn just as `vuk it` draws them. Bottom: the **game**: whose turn it is, the ball, every player's score, and the running modes with their priorities |
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

## Placing things on the playfield

Without any config, the playfield is laid out for you:
- ball device switches sit in a row at the bottom;
- autofire switches (slingshots, pop bumpers) sit on their side, from
  `left` or `right` in their name;
- cabinet switches (start, flipper buttons, tilt, coin door…) stay off the
  playfield, in the switches pane only;
- everything else goes in a grid at the top.

To put a switch or light where it really is, give its position in a
`dashboard:` section, from the playfield's bottom-left corner:

```yaml
dashboard:                # vuk me only: where things sit on its virtual playfield
  playfield:
    s_target: [0.5, 0.62] # [x, y], each from 0 to 1
    l_frenzy: [0.5, 0.54]
```

The names must be switches or lights in the config. This section describes
the machine, so it's YAML.

## Status (0.0.x)

Works: everything above, on the simulated platforms. Planned:
- dragging things on the playfield and saving their positions;
- a choice of playfield and backglass artwork templates;
- trying it against real hardware (FAST Nano) with `--hardware`.

## Coming from MPF

| MPF | vukery |
|---|---|
| `mpf both` plus `mpf monitor` | `vuk me` |
| MPF Monitor's `monitor.yaml` positions | `dashboard: playfield:` in the machine config |
| clicking a switch in MPF Monitor | clicking it on the dashboard (right-click locks it) |
