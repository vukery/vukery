# Built-in modes

vukery ships the modes every pinball machine needs. Today that's **attract**,
**game**, **[high score](high-score.md)** and **[tilt](tilt.md)**; replay,
match and the others are planned. (Ball saves and ball search are
[devices](../../devices/ball-saves.md), as in MPF.) Core modes always run;
optional ones run when the game lists them in `modes:`. A game changes a
built-in mode only in the ways it declares, never by copying its code and
editing it.

**Customizing:** a built-in mode lists what can change (its
`customizable`), in three kinds:

- **settings:** class attributes, such as high score's categories;
- **look:** the scene, sound or show for each moment, such as the
  initials screen;
- **hooks:** a few methods with a fixed signature that return a
  decision, such as what a replay pays.

Change them in a subclass, in the mode's folder, and list the mode in
`modes:` as usual:

```python
# modes/high_score/mode.py
from vukery.modes import HighScore


class CombatHighScore(HighScore):   # still the high_score mode
    enter_initials_seconds = 45
```

**Anything else is refused** when the class is defined: overriding another
method (`mode_start`, say) or setting, or adding an `@on` handler. The error
says what the mode can change. For more behavior, react to the built-in
mode's events in a mode of your own.

**Replacing:** the *optional* built-in modes (high score, replay, match and
the like) can be replaced outright. A mode of the game's own with the same
name, not a subclass, runs instead. The *core* ones, attract and game, can't
be replaced, only customized.

| Built-in mode | Kind | Can change |
|---|---|---|
| `attract` | core | nothing yet |
| `game` | core | nothing yet (balls and players are in `game:`) |
| [`high_score`](high-score.md) | optional | `categories`, `defaults`, `enter_initials_seconds`, `award_seconds`, `look` |
| [`tilt`](tilt.md) | optional | `warnings_to_tilt`, `multiple_hit_window`, `settle_time`, `reset_warnings_events`, the switch tags, `tilt_warnings_player_var`, `look` |
