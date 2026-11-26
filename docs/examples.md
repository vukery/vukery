# Examples

The `examples/` folder holds complete games, kept dead simple on purpose.
More will be added as vukery grows.

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
uv run vuk run          # then type s_start, s_target, s_left_sling…
uv run pytest           # the specs
```

The files:

| File | What's in it |
|---|---|
| `config/machine.yaml` | switches, coils, the trough, flippers, slingshots, `game:` and `modes:` |
| `config/environments/development.yaml` | logging for development |
| `modes/base/base.py` | the scoring |
| `tests/test_basic.py` | the specs |

## `examples/display` (coming next)

The same machine with one display: the score and ball number, drawn by the
pyglet media controller.
