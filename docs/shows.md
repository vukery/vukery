# Shows

!!! note "0.0.x"
    Shows drive lights, coils and events over time. Sounds, scenes and other
    shows inside a show come later, and so do effects computed from where
    lights sit on the playfield.

A show is a YAML file in the folder of the mode it belongs to:
`modes/flash_score/bumper_flash.yaml` is the show `flash_score.bumper_flash`.
Its own mode plays it by its short name; another mode uses the full name.

```python
class FlashScore(Mode):
    def mode_start(self, **_):
        self.play_show("bumper_flash", loops=-1, show_tokens={"color": "ffffff"})
```

## Two ways to write one

### Frames: a grid over lights

Most shows light a set of lights in a pattern. A **frames** show draws it as
a grid: one row per moment, one column per light.

```yaml
# modes/hole_score/lane_sweep.yaml
every: 0.15s                  # each row lasts this long
lights: hole_score_lanes      # a light group (or a light, or a list): its lights are the columns
colors: {R: ff0000, O: ff8000, Y: ffff00}
frames: |
  R.........
  RR........
  RRO.......
  RROO......
  RROOO.....
  RROOOY....
```

| In a row | Means |
|---|---|
| a letter | on, in that letter's color from `colors:` |
| `.` | off |
| `-` | leave this light alone |
| a space | nothing: use spaces to line columns up |

- **Columns follow the order of the lights,** and a light group stands for
  its lights in the group's order. `lights: [bumper1_ring, bumper2_ring]`
  makes the first ring's lights the first columns.
- **A row must have one mark per light;** vukery says which row doesn't.
- **To hold a frame longer,** repeat the row.

### Steps: MPF's show format

For coils, events, fades or timing by hand, a show is MPF's list of steps,
and MPF shows copy over:

```yaml
# modes/match/match_chimes.yaml
- time: 0
  coils: c_chime1
- time: +0.25s                # relative to the step before
  coils: c_chime3
  lights: {l_match: {color: ffcc00, fade: 200ms}}
- time: +0.4s
  events: match_chimed
```

- **Timing:** `time:` is absolute, or relative with `+`; `duration:` is the
  step's length. `duration: -1` holds until the show is stopped. Times take
  `0.5`, `500ms` or `0.5s`.
- **`lights:`** takes a light or a group, and a color (`ff8800`), `on`, `off`,
  or `{color: ..., fade: ...}`.
- **`coils:`** takes a coil or a list (each is pulsed), or
  `{c_x: {action: enable}}` (`pulse`, `enable`, `disable`). Coils keep their
  limits: a show can't pulse harder or longer than the coil allows.
- **`events:`** takes an event or a list, posted when the step runs.

## Tokens

`(name)` anywhere in a show is a **token**, filled in when the show plays.
That works in names and in values:

```yaml
# modes/base/lit.yaml
- duration: -1
  lights: {(lights): (color)}
```

```python
self.play_show("lit", show_tokens={"lights": "hole_score_lanes", "color": "00ff00"})
```

A token can be a whole light group, so one show works for any set of lights.
Playing a show with a token it doesn't have is an error.

## Playing a show

`self.play_show(name, ...)` takes MPF's `show_player` options:

| Option | Default | |
|---|---|---|
| `priority` | `0` | added to the mode's priority |
| `speed` | `1.0` | `2` plays twice as fast |
| `loops` | `-1` | how many times to repeat; `-1` forever, `0` plays once |
| `start_step` | `1` | where to start; negative counts from the end |
| `show_tokens` | none | values for the show's tokens |
| `key` | the show's name | playing again under the same key replaces the running show |
| `events_when_played`, `events_when_stopped`, `events_when_looped`, `events_when_completed` | none | events to post |

It returns the running show: `stop()`, `pause()`, `resume()` and
`advance()`. `self.stop_show("lane_sweep")` stops one of the mode's shows by
key, and `self.stop_show()` stops them all.

**A show only borrows its lights.** Each light keeps a stack of colors by
priority, as in MPF. A show puts its colors on that stack under its own
key, so:
- a higher-priority show covers a lower one, and the lower one shows again
  when it stops;
- when a show stops, its lights go back to whatever was there before;
- **a mode's shows stop when the mode stops.**

## MPF's built-in shows

`on`, `off`, `led_color`, `flash` and `flash_color` work as in MPF, with the
tokens `lights` (a light or a group) and `color`:

```python
self.play_show("flash_color", speed=4, show_tokens={"lights": "shoot_again", "color": "ff8000"})
```

## Light groups

Shows (and modes) work on **light groups**: ordered lists of lights in
`machine.yaml`.

```yaml
light_groups:
  hole_score_lanes: l_lane_1, l_lane_2, l_lane_3   # or a list
```

A group does what a light does: `self.machine.light_groups["hole_score_lanes"].color("ff0000")`.

## Checked as the machine starts

vukery loads every show when the machine starts, and stops with a clear
message for:
- a light, group or coil that doesn't exist;
- a frame row with the wrong number of columns, or a letter with no color;
- a time it can't read;
- a section it doesn't support yet (`sounds:`, `slides:`, `widgets:`,
  `shows:`).

## Coming from MPF

| MPF | vukery |
|---|---|
| `shows/bumper_flash.yaml` | `modes/<mode>/bumper_flash.yaml`, a show belongs to a mode |
| `show_player: event: show_name` | `self.play_show("show_name")` in a handler |
| `show_player` options | the same names on `play_show` |
| `show_tokens` | `show_tokens=`, and tokens can be whole light groups |
| `(light1)` … `(light5)` tokens for a list of lights | one token naming a light group |
| a light listed in every step | a `frames` grid over a light group |
| light tags in shows | light groups |
| `light_player` | a show, or `light.color(...)` in Python |
