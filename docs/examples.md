# Examples

The `examples/` folder holds complete games, kept dead simple on purpose.
More will be added as vukery grows.

| Example | Displays | Shows |
|---|---|---|
| `basic` | none | the game engine, modes, scoring, tests |
| `display` | one | slides with live values |
| `dual_display` | two | a media controller per display, slides per display |

## `examples/basic`

The smallest complete vukery game, with no display or sound:

- a trough with three balls;
- a start button;
- two flippers and two slingshots;
- one target;
- a `base` mode that scores 1000 for the target and 10 for each slingshot.

It has 14 specs covering attract, starting a game (and refusing to start
unless every ball is home), scoring, draining, game over, and two players
taking turns.

```console
cd examples/basic
uv run vuk it          # then type s_start, s_target, s_left_sling…
uv run pytest           # the specs
```

The files:

| File | What's in it |
|---|---|
| `config/machine.yaml` | switches, coils, the trough, flippers, slingshots, `game:` and `modes:` |
| `config/environments/development.yaml` | logging for development |
| `modes/base/base.py` | the scoring |
| `tests/test_basic.py` | the specs |

## `examples/display`

`examples/basic` plus one 800×480 display, drawn by the pyglet media
controller:

- a `start_screen` mode shows "PRESS START" between games;
- the `base` mode shows the score, player and ball during a game.

Its 6 specs check what's on screen from game start to game over, including
two players taking turns.

```console
cd examples/display
uv run vuk it          # opens the display window; type s_start, s_target…
uv run pytest
```

| File | What's in it |
|---|---|
| `config/machine.yaml` | `examples/basic`'s machine, plus `displays:` |
| `modes/start_screen/start_screen.py` | the slide shown between games |
| `modes/base/base.py` | scoring and the score slide |
| `tests/test_display.py` | the specs |

## `examples/dual_display`

`examples/basic` with two displays: an 800×480 main screen and a 480×272
apron screen. `vuk it` opens two windows, one media controller process
each.

| Display | Between games | During a game |
|---|---|---|
| `main` | the title | the score |
| `apron` | "PRESS START" | the player and ball |

Each mode shows its slides on specific displays:

```python
def mode_start(self, **_):
    self.show_slide("score", display="main")
    self.show_slide("ball_info", display="apron")
```

Its 7 specs check that a media controller loads for each display and what
each display shows, from the title screen through a two-player game and back.

```console
cd examples/dual_display
uv run vuk it
uv run pytest
```
