# Testing a game

vukery games are tested with RSpec-style specs (pytest with
[pytest-describe](https://pypi.org/project/pytest-describe/)), on virtual
time: a test of a whole 3-ball game runs in a fraction of a second.

```python
from pathlib import Path

import pytest

from vukery.testing import GameRig, expect


@pytest.fixture
def game():
    rig = GameRig(Path(__file__).parents[1])   # the game folder
    yield rig
    rig.stop()


def describe_base_mode():
    def it_scores_the_target(game):
        game.start_game()
        game.switch("s_target")
        expect(game.player.score).to_equal(1000)

    def describe_after_a_drain():
        def it_starts_ball_two(game):
            game.start_game()
            game.drain()
            expect(game.player.ball).to_equal(2)
```

Run them with `uv run vuk you` from the machine folder (`vuk test` is the
same command). It:
- always uses the test environment;
- measures how much of the machine's code (`modes/`) the specs run, and
  prints the coverage after the results (`--no-cov` turns that off);
- passes any other arguments to pytest, e.g. `uv run vuk you -k scoring`.

Coverage needs pytest-cov, which machines made with `vuk it` have. In an
older machine, add it with `uv add --dev pytest-cov`.

The specs print as a tree:

```text
Base mode:
  ✓ It scores the target

  After a drain:
    ✓ It starts ball two
```

## The rig

`GameRig(game_folder)` runs the game in the `test` environment. Nothing
happens until the test does something.

| Option | Default | |
|---|---|---|
| `fill_troughs` | `True` | Every trough switch starts active (all balls home); other ball devices start empty |
| `simulate_balls` | `True` | An ejected ball leaves the trough by itself, and lands in its eject target (a plunger lane, say) |

### Actions

| | |
|---|---|
| `game.switch("s_target")` | Tap a switch (active, then inactive) |
| `game.switch("s_a", "s_b")` | Several switches at the same moment |
| `game.switch("s_hole", state="active")` | Set a switch and leave it |
| `game.switch("s_hole", hold=2)` | Tap, holding it for 2 seconds |
| `game.switch("s_spinner", times=5, every=0.05)` | Repeated taps |
| `game.advance(3)` | Let 3 seconds pass |
| `game.start_game(players=2)` | Press start (a switch tagged `start`) once per player |
| `game.drain()` | Return a ball to the trough (a ball waiting in a plunger lane is shot first) |
| `game.post("event_name", **args)` | Post an event |

There's one method per action. "Hold a switch, then wait" is two calls:

```python
game.switch("s_hole", state="active")
game.advance(2)
```

### What you can check

| | |
|---|---|
| `game.player` | The current player (`.score`, `.ball`, `.number`, your variables) |
| `game.game` | The running game, or `None` |
| `game.mode("base")` | A mode |
| `game.switches("s_target")` | A switch |
| `game.machine` | Everything else |

### Expectations

| | |
|---|---|
| `expect(value).to_equal(x)` | |
| `expect(game.mode("base")).to_be_running()` / `.to_be_stopped()` | |
| `expect(game.switches("s_hole")).to_be_active()` / `.to_be_inactive()` | |
| `expect(game).to_have_posted("ball_started")` | posted at least once |
| `expect(game).to_have_posted("ball_started", times=2)` | exactly twice |
| `expect(game).not_to_have_posted("game_ended")` | |

## Coming from MPF

| MPF test case | vukery |
|---|---|
| `hit_and_release_switch("s")` | `game.switch("s")` |
| `hit_switch_and_run("s", t)` | `game.switch("s", state="active")` then `game.advance(t)` |
| `release_switch_and_run("s", t)` | `game.switch("s", state="inactive")` then `game.advance(t)` |
| `hit_and_release_switches_simultaneously(["a", "b"])` | `game.switch("a", "b")` |
| `advance_time_and_run(t)` | `game.advance(t)` |
| `start_game()` | `game.start_game()` |
| `drain_one_ball()` | `game.drain()` |
| `assertModeRunning("base")` | `expect(game.mode("base")).to_be_running()` |
| `assertPlayerVarEqual(1000, "score")` | `expect(game.player.score).to_equal(1000)` |
| `assertEventCalled("x")` (with `mock_event`) | `expect(game).to_have_posted("x")` |
