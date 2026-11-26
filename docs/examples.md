# Examples

The [`examples/`](https://github.com/vukery/vukery/tree/main/examples) folder holds complete games,
kept dead simple on purpose. More will be added as vukery grows.

**They're meant to be copied.** Browse them on GitHub and copy whatever you
like: a mode, a config section, a spec. Or start a game from a whole
example:

```console
git clone --depth 1 https://github.com/vukery/vukery.git
cp -r vukery/examples/basic my_game
```

| Example | Displays | Shows |
|---|---|---|
| [`basic`](https://github.com/vukery/vukery/tree/main/examples/basic) | none | the game engine, modes, scoring tables, priority and blocking, tests |
| [`display`](https://github.com/vukery/vukery/tree/main/examples/display) | one | slides with live values |
| [`dual_display`](https://github.com/vukery/vukery/tree/main/examples/dual_display) | two | a media controller per display, slides per display |

## `examples/basic`

[Browse it on GitHub](https://github.com/vukery/vukery/tree/main/examples/basic)

The smallest complete vukery game, with no display or sound:

- a trough with three balls;
- a start button;
- two flippers and two slingshots;
- one target;
- a `base` mode that scores 1000 for the target and 10 for each slingshot,
  and lights Frenzy on every third target;
- a `frenzy` mode (higher priority, 10 seconds) that shows priority and
  scoring blocks. Its target scores 5000 *instead of* Base's 1000, and its
  slingshots score 100 *as well as* Base's 10.

Its 22 specs cover:
- attract;
- starting a game, and refusing to start unless every ball is home;
- scoring, draining and game over;
- Frenzy's blocking, timing and ending with the ball;
- two players taking turns.

The config, modes and specs are commented, as a starting point for your own
game.

```console
cd examples/basic
uv run vuk me          # click s_start, then s_target, s_left_sling…
uv run pytest           # the specs
```

The files:

| File | What's in it |
|---|---|
| [`config/machine.yaml`](https://github.com/vukery/vukery/blob/main/examples/basic/config/machine.yaml) | switches, coils, a light, the trough, flippers, slingshots, `game:`, `dashboard:` and `modes:` |
| [`config/environments/development.yaml`](https://github.com/vukery/vukery/blob/main/examples/basic/config/environments/development.yaml) | logging for development |
| [`modes/base/base.py`](https://github.com/vukery/vukery/blob/main/examples/basic/modes/base/base.py) | the scoring table, and lighting Frenzy |
| [`modes/frenzy/frenzy.py`](https://github.com/vukery/vukery/blob/main/examples/basic/modes/frenzy/frenzy.py) | priority, `Score(block=True)`, a timed mode, a light |
| [`tests/test_basic.py`](https://github.com/vukery/vukery/blob/main/examples/basic/tests/test_basic.py) | the specs |

## `examples/display`

[Browse it on GitHub](https://github.com/vukery/vukery/tree/main/examples/display)

`examples/basic` plus one 800×480 display, drawn by the pyglet media
controller:

- a `start_screen` mode shows "PRESS START" between games;
- the `base` mode shows the score, player and ball during a game.

Its 7 specs check what's on screen from game start to game over, including
two players taking turns.

```console
cd examples/display
uv run vuk me          # the display shows in the dashboard's backbox
uv run pytest
```

| File | What's in it |
|---|---|
| [`config/machine.yaml`](https://github.com/vukery/vukery/blob/main/examples/display/config/machine.yaml) | `examples/basic`'s machine, plus `displays:` |
| [`modes/start_screen/start_screen.py`](https://github.com/vukery/vukery/blob/main/examples/display/modes/start_screen/start_screen.py) | the slide shown between games |
| [`modes/base/base.py`](https://github.com/vukery/vukery/blob/main/examples/display/modes/base/base.py) | scoring and the score slide |
| [`tests/test_display.py`](https://github.com/vukery/vukery/blob/main/examples/display/tests/test_display.py) | the specs |

## `examples/dual_display`

[Browse it on GitHub](https://github.com/vukery/vukery/tree/main/examples/dual_display)

`examples/basic` with two displays: an 800×480 main screen and a 480×272
apron screen. `vuk us` opens two full-screen windows, one media controller
process each; `vuk me` shows both in its backbox.

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
uv run vuk me
uv run pytest
```
