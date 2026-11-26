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

Game logic lives in modes: Python classes in `modes/<name>/<name>.py`.

```python
from vukery import Mode


class Base(Mode):
    priority = 100               # higher runs first, and can block lower
    start_on = "ball_started"    # starts with every ball

    scoring = {                  # MPF: variable_player
        "s_target": 1000,
        "s_left_sling": 10,
    }
```

The [Modes](modes.md) page covers everything about them:
- settings and priority;
- scoring tables;
- blocking;
- score adjusters (multipliers);
- handlers and player variables;
- the lifecycle;
- a "coming from MPF" table.

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
uv run vuk me
```

In development the machine is simulated. The [dashboard](dashboard.md)
shows the whole machine: click `s_start` to start a game, then click
switches on the playfield. Esc stops it. Logs go to `log/development.log`.

On the machine itself, `vuk it` runs the game with its displays full screen
(see [The vuk command](cli.md)).

## Coming from MPF

The section names in config are MPF's. Game logic moves from YAML to modes:
see [Modes: Coming from MPF](modes.md#coming-from-mpf).
