# Writing a game

!!! note "0.0.x"
    The game engine runs on the simulated `development` and `test`
    platforms: switches, coils, lights, a simple trough, single-wound
    flippers, autofire coils, the attract and game modes, and your own
    modes, and text slides on displays ([Displays and slides](displays.md)).
    Ball saves, tilt, shows and sound come later. The complete examples are
    [`examples/basic` and `examples/display`](examples.md).

## A game folder

```text
my_game/
  config/
    machine.yaml              the machine: switches, coils, devices, settings
    environments/
      development.yaml        overrides for development (optional)
      test.yaml               overrides for tests (optional)
      production.yaml         overrides for the real machine
  modes/
    base/
      base.py                 class Base(Mode)
  tests/
    test_my_game.py           specs
```

`config/` can hold any number of `.yaml` files. They're merged in
alphabetical order, then the environment's file (or every file in an
`environments/<name>/` folder) is merged on top.

## The machine (YAML)

YAML describes the machine. Sections and settings are MPF's:

```yaml
switches:
  s_start:
    number: "0"
    tags: start               # the start button
  s_trough1: {number: "1"}
  s_trough2: {number: "2"}
  s_target:  {number: "8"}

coils:
  c_trough_eject:
    number: "0"
    default_pulse_ms: 20

ball_devices:
  bd_trough:
    ball_switches: s_trough1, s_trough2
    eject_coil: c_trough_eject
    tags: trough, home, drain

flippers:
  left_flipper:
    main_coil: c_left_flipper
    activation_switch: s_left_flipper

autofire_coils:
  left_sling:
    coil: c_left_sling
    switch: s_left_sling

game:
  balls_per_game: 3           # default 3
  max_players: 4              # default 4

modes:
  - base
```

**Supported sections so far:** `switches`, `coils`, `lights`,
`ball_devices` (troughs), `flippers` (single-wound, no EOS),
`autofire_coils`, `game`, `modes`, `player_vars`, `displays`, `media`,
`hardware`, `fast`, `logging`.

**Game logic sections aren't allowed.** vukery stops with an error that
points you to modes if your config has `variable_player`, `event_player`,
`show_player`, `slide_player` or any other MPF config player.

## Modes (Python)

Game logic lives in modes. A mode is a class that extends `Mode`, in
`modes/<name>/<name>.py`, named for what it does:

```python
from vukery import BLOCK, Mode, on


class Base(Mode):
    priority = 100
    start_on = "ball_started"

    @on.switch("s_target")
    def target(self):
        self.score(1000)

    @on.switch("s_left_sling")
    @on.switch("s_right_sling")
    def sling(self):
        self.score(10)
```

### Mode settings

| Setting | Default | What it does | MPF |
|---|---|---|---|
| `priority` | `100` | Higher runs first; a mode's handlers run at its priority | `mode: priority` |
| `start_on` | none | Event name(s) that start the mode | `start_events` |
| `stop_on` | none | Event name(s) that stop it | `stop_events` |
| `game_mode` | `True` | Only runs during a game, and stops when it ends | `game_mode` |
| `stop_on_ball_end` | `True` | Stops at the end of each ball | `stop_on_ball_end` |
| `name` | from the class | `HoleScore` → `hole_score` | the mode folder name |

For code that runs the whole time the machine is on, set `game_mode = False`
and `start_on = "reset_complete"`.

### Reacting to things

| Decorator | Runs when |
|---|---|
| `@on.switch("s_target")` | the switch goes active |
| `@on.switch("s_target", state="inactive")` | it goes inactive |
| `@on.switch("s_hole", hold=2)` | it has stayed active for 2 seconds |
| `@on.event("ball_started")` | the event is posted; the method gets its arguments |

**Blocking (MPF's `|block`).** Return `BLOCK` from a handler to stop
lower-priority modes from handling the same switch hit or event.

### What a mode can do

| | |
|---|---|
| `self.score(points)` | Add to the current player's score |
| `self.player` | The current player: `self.player.score`, `self.player.ball`, your own variables |
| `self.post("event_name", **args)` | Post an event |
| `self.delay("name", seconds, callback)` | Call later; cancelled when the mode stops |
| `self.cancel_delay("name")` | |
| `mode_start()` / `mode_stop()` | Override to run code as the mode starts or stops |
| `self.machine` | Everything else: `switches`, `coils`, `lights`, `events`, `game` |

### Player variables

Set any attribute on a player and it becomes a player variable:
`self.player.ramps += 1`. Each change posts `player_<name>` with `value`,
`prev_value`, `change` and `player_num`, as in MPF. Starting values can go in
config:

```yaml
player_vars:
  ramps:
    initial_value: 0
```

## Events

vukery's events follow MPF's rules, so code and timing carry over:

- posting never runs handlers immediately;
- higher priority first, and equal priorities in the order they were added;
- events posted by a handler run before the rest of the queue;
- boolean, relay and queue events work as in MPF.

### The events a game posts

```text
game_will_start → game_starting (queue) → game_started
  player_turn_will_start → player_turn_starting (queue) → player_turn_started
  ball_will_start → ball_starting (queue) → ball_started
    … the ball drains (ball_drain, a relay) …
  ball_will_end → ball_ending (queue) → ball_ended
  player_turn_will_end → player_turn_ending (queue) → player_turn_ended
game_will_end → game_ending (queue) → game_ended
```

A switch tagged `start` posts `sw_start`. In attract it asks to start a game
(`request_to_start_game`, which is refused unless every ball is home). During
the first ball it adds a player.

Every switch posts `<switch>_active` and `<switch>_inactive`. Modes post
`mode_<name>_started` and `mode_<name>_stopped`.

## Run it

```console
cd my_game
uv run vuk it
```

In development the machine is simulated. Type a switch name and press Enter
to tap it, for example `s_start` and then `s_target`. Logs go to
`log/development.log`.

## Coming from MPF

| MPF | vukery |
|---|---|
| `mode:` YAML, plus `code:` | A `Mode` class in `modes/<name>/<name>.py` |
| `variable_player: s_target_active: score: 1000` | `@on.switch("s_target")` and `self.score(1000)` |
| `score: 1000\|block` | `return BLOCK` |
| `event_player` | `self.post(...)` |
| conditional events (`event{condition}`) | an `if` in the handler |
| `CustomCode` | a `Mode` with `game_mode = False` |
