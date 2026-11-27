# Modes

Game logic lives in modes. A mode is a Python class that extends `Mode`, in
`modes/<name>/mode.py`, listed under `modes:` in the config. Name it for
what it does (`HoleScore`, `Frenzy`). vukery has no `CustomCode`: anything
that hooks into the machine is a mode.

```python
from vukery import Mode, Score, on


class Frenzy(Mode):
    priority = 200
    start_on = "frenzy_lit"

    scoring = {
        "s_target": Score(5000, block=True),
        "s_left_sling": 100,
    }

    def mode_start(self, **_):
        self.delay("over", 10, self.stop)
```

The complete, commented example is `examples/basic` (its `base` and `frenzy`
modes).

## A mode's files

A mode is a folder, and its main file is always `mode.py`.

- **`mode.py` holds the class and everything that configures the mode:**
  its settings (priority, `start_on`…) and its scoring table.
- **Bigger parts go in files next to it,** imported with a relative import:
  - its scenes in `scenes.py`;
  - its shows, as YAML files (see [Shows](../media/shows.md));
  - helper code in a module of its own.

```text
modes/base/
  mode.py       the Mode class: settings, scoring table, rules
  scenes.py     @scene functions
  lane_sweep.yaml  a show
```

```python
# modes/base/mode.py
from vukery import Mode

from .scenes import score   # a file next to this one


class Base(Mode):
    priority = 100
    start_on = "ball_started"
    scoring = {"s_target": 1000, "s_left_sling": 10}
    scenes = (score,)
```

- **Any Python file name works;** `scenes.py` is a convention. Every
  `.yaml` file in the folder is a show.
- **A small mode can stay in one file,** as in `examples/basic`. Both ways
  load the same.
- **Every folder in `modes/` is a mode**, so each needs a `mode.py`; vukery
  checks when the machine starts. The exceptions are `modes/vukery/`
  (reserved for overrides) and folders inside a mode.

## Settings

Settings are class attributes:

| Setting | Default | What it does | MPF |
|---|---|---|---|
| `priority` | `100` | Higher runs first and can block lower (see [Priority](#priority)) | `mode: priority` |
| `start_on` | none | Event name, or a tuple of names, that start the mode | `start_events` |
| `stop_on` | none | Event name(s) that stop it | `stop_events` |
| `game_mode` | `True` | Only runs during a game, and stops when it ends | `game_mode` |
| `stop_on_ball_end` | `True` | Stops at the end of each ball | `stop_on_ball_end` |
| `use_wait_queue` | `False` | Started by a queue event (such as `game_ending`), holds it until the mode stops: the game ends after it | `use_wait_queue` |
| `scoring` | `{}` | What the mode scores (see [Scoring](#scoring)) | `variable_player` |
| `scenes` | `()` | The `@scene` functions the mode can show (see [Displays and scenes](../media/scenes.md)) | `slides` / `slide_player` |
| `name` | from the class | `HoleScore` → `hole_score` | the mode's folder name |

For code that runs the whole time the machine is on, set `game_mode = False`
and `start_on = "reset_complete"`.

## Priority

**Where it's set:** `priority` on the mode class. It isn't in YAML.

**What it decides:**
- **Order:** when a switch is hit or an event is posted, every running
  mode's handlers run highest priority first.
- **Blocking:** a mode can stop lower-priority modes' scoring for the same
  hit (see [Blocking](#blocking)). It can never block a mode above it.
- **Scenes:** a scene's priority is its mode's priority plus the
  `priority=` passed to `show_scene()`, and each display shows its highest.
- **Shows:** a show's priority is its mode's priority plus the `priority=`
  passed to `play_show()`, and each light shows its highest.

**The built-in modes:** attract is `10` and game is `20`, as in MPF. Use
`100` and up for your own game modes.

A single handler can be nudged within its mode:
`@on.switch("s_hole", priority=5)` runs at the mode's priority plus 5.

## Scoring

A `scoring` table lists what a mode scores. It's the Python equivalent of
MPF's `variable_player`:

```python
from vukery import Award, Mode, Score


class Base(Mode):
    scoring = {
        "s_target": 1000,                                    # a switch: points when it's hit
        "sw_pops": 100,                                      # a switch tag (any switch tagged pops)
        "ramp_made": 2500,                                   # any event
        "s_spinner": lambda mode: 10 * mode.player.lanes,    # computed when it's hit
        "s_hole": Score(5000, block=True),                   # blocks lower modes (see below)
        "s_lane": Award(lanes=1),                            # another player variable, not the score
    }
```

- **Keys** are switch names (scoring when the switch goes active), switch
  tag events (`sw_<tag>`) or any event name. vukery warns if a key looks
  like a switch (`s_…`) but isn't one.
- **Values:**
  - a number of points;
  - a function that gets the mode and returns points;
  - `Score(points, block=…)`;
  - `Award(variable=amount, …, block=…)`.
- **Only while the mode runs:** the table is active from the time the mode
  starts until it starts stopping.
- **One entry per key, per mode.** For more on the same switch, add a
  handler (see [Reacting to things](#reacting-to-things)).
- **To score from code,** call `self.score(points)`. It goes through the
  same adjusters.

**Reusing a table:** a subclass can build on its parent's.

```python
class HardBase(Base):
    scoring = Base.scoring | {"s_target": 2500}
```

## Blocking

There are two ways a mode can change what lower-priority modes do.

### `Score(..., block=True)`: replace their points for one switch

A higher-priority mode's value replaces a lower one's, instead of adding to
it. This is MPF's `|block`.

```python
class Base(Mode):            # priority 100
    scoring = {"s_target": 1000, "s_left_sling": 10}

class Frenzy(Mode):          # priority 200
    scoring = {
        "s_target": Score(5000, block=True),  # 5000, not 6000
        "s_left_sling": 100,                  # no block: 100 + 10 = 110
    }
```

- **It only blocks scoring** of that variable. The lower mode's other
  handlers for the same switch, such as a sound or a light, still run. In
  `examples/basic`, Base keeps counting targets with an ordinary handler
  while Frenzy blocks its points.
- **Blocking is per variable.** Blocking `score` doesn't block an
  `Award(lanes=1)` on the same switch.
- **Equal priorities aren't blocked,** as in MPF.

**Only when a condition holds:**

```python
"s_hole": Score(5000, block=lambda mode: mode.player.hole_lit),
```

### `return BLOCK`: stop everything below

A handler that returns `BLOCK` stops every lower-priority mode's handlers
for that switch or event, scoring and everything else:

```python
from vukery import BLOCK

@on.switch("s_hole")
def captured(self):
    self.start_hole_award()
    return BLOCK
```

## Score adjusters

A mode can change **every** score while it runs by overriding
`adjust_score`. Points pass through every running mode's adjuster, highest
priority first, then get rounded to a whole number.

```python
class Multiplier(Mode):      # playfield X, written once instead of on every scoring line
    def adjust_score(self, points, source):
        return points * self.player.multiplier

class RedLine(Mode):         # at the red line, only the target still scores
    def adjust_score(self, points, source):
        return points if source == "s_target" else 0
```

- `source` is the switch or event that scored (from a scoring table), or
  whatever was passed to `self.score(points, source)`.
- `Award` variables don't go through adjusters; only the score does.

**Block or adjust?** Use `block` when one switch is worth something different
while a mode runs. Use `adjust_score` when a rule changes all scoring
(multipliers, "nothing scores at the red line").

## Reacting to things

| Decorator | Runs when |
|---|---|
| `@on.switch("s_target")` | the switch goes active |
| `@on.switch("s_target", state="inactive")` | it goes inactive |
| `@on.switch("s_hole", hold=2)` | it has stayed active for 2 seconds |
| `@on.event("ball_started")` | the event is posted; the method gets its arguments |

A method can take several decorators. A switch can have a handler and a
scoring entry in the same mode.

## What a mode can do

| | |
|---|---|
| `self.player` | the current player: `score`, `ball`, `number`, and any variable you set |
| `self.score(points, source=None)` | add points, through the adjusters |
| `self.post("event_name", **args)` | post an event |
| `self.delay("name", seconds, callback)` | call later; cancelled if the mode stops first |
| `self.cancel_delay("name")` | |
| `self.show_scene(scene, display=None, priority=0)` / `self.remove_scene(scene)` | see [Displays and scenes](../media/scenes.md) |
| `self.publish(**values)` | values for scenes, as `{<mode name>.<key>}`: see [values from modes](../media/scenes.md#values-from-modes) |
| `self.play_show(name, ...)` / `self.stop_show(key=None)` | see [Shows](../media/shows.md) |
| `self.stop()` | stop the mode |
| `self.machine` | everything else: `switches`, `coils`, `lights`, `events`, `game`, `modes` |
| `mode_start()` / `mode_stop()` | override to run code as the mode starts or stops |

**Player variables** are plain attributes: `self.player.ramps += 1`. Each
change posts `player_<name>` with `value`, `prev_value`, `change` and
`player_num`. `self.player.get("ramps", 0)` reads one that might not be set
yet. Starting values can go in config:

```yaml
player_vars:
  ramps:
    initial_value: 0
```

## Built-in modes

vukery ships the modes every pinball machine needs: attract and game, and
optional ones a game lists in `modes:`, such as high score and tilt. A game
changes one only in the ways it declares. See [Built-in modes](built-in/index.md).

## Lifecycle

Starting and stopping post MPF's events, in this order:

```text
start:  mode_<name>_will_start → mode_<name>_starting (queue) → (active) → mode_<name>_started → mode_start()
stop:   mode_<name>_will_stop  (switch handlers and scoring end, delays cancelled)
        → mode_<name>_stopping (queue) → mode_<name>_stopped → mode_stop() → (handlers, scenes and shows removed)
```

A mode stops on its `stop_on` events, at the end of each ball
(`stop_on_ball_end`), when the game ends (`game_mode`), or when it calls
`self.stop()`.

## Coming from MPF

| MPF | vukery |
|---|---|
| `mode:` YAML plus `code:` | a `Mode` class in `modes/<name>/mode.py` |
| `mode: priority: 200` | `priority = 200` |
| `start_events` / `stop_events` | `start_on` / `stop_on` |
| `variable_player: s_target_active: score: 1000` | `scoring = {"s_target": 1000}` |
| `score: 5000\|block` | `Score(5000, block=True)` |
| `variable_player: s_lane_active: lanes: 1` | `Award(lanes=1)` |
| `score: 50 * current_player.multiplier` on every line | one `adjust_score` in a multiplier mode |
| `score: (1 - current_player.red_line) * …` | `adjust_score` returning 0 |
| conditional events (`event{condition}`) | an `if` in a handler, or a function in the scoring table |
| `event_player` | `self.post(...)` |
| `CustomCode` | a `Mode`, often with `game_mode = False` |
