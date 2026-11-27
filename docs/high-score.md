# High score

!!! note "0.0.x"
    Built: categories, initials with the flippers and start, the award
    screens, saved tables. Replay, match and the other optional built-in
    modes come later.

An optional [built-in mode](modes.md#built-in-modes), as MPF's
`high_score`. List it in `modes:` to use it:

```yaml
modes:
  - base
  - high_score      # vukery's, as it is (or customized in modes/high_score/)
```

When a game ends, it holds the end (MPF's `use_wait_queue`) while every
player who beat an entry, in turn:

1. **enters initials:** the flipper buttons (switches tagged `left_flipper`
   and `right_flipper`) choose a letter, start (`start`) takes it; three
   letters, or until time runs out (`???` if nothing was taken);
2. **sees each award** for a few seconds.

Then the tables are saved in `data/high_scores.yaml` in the machine folder
(new machines keep `data/` out of git) and the game ends. In specs, the rig
keeps them in a temporary folder instead, so a spec run never changes them. A score that ties
an entry doesn't beat it.

## Customizing it

In `modes/high_score/mode.py`, a subclass changes what it declares, and
nothing else:

```python
from vukery.modes import HighScore

from .scenes import award, initials


class CombatHighScore(HighScore):
    categories = {                      # player variable: its labels, best first
        "score": ["AMMIRAGLIO", "PUNTEGGIO ELEVATO 1", "PUNTEGGIO ELEVATO 2",
                  "PUNTEGGIO ELEVATO 3", "PUNTEGGIO ELEVATO 4"],
        "multiball_score": ["DUE PALLE CAMPIONE", "SECONDO DUE PALLE"],
    }
    defaults = {                        # the starting tables
        "score": [("ZAC", 240_000), ("CAR", 200_000), ("RIA", 150_000), ("COM", 100_000), ("BAT", 50_000)],
        "multiball_score": [("ZAC", 1_000), ("CAR", 500)],
    }
    enter_initials_seconds = 45
    award_seconds = 4
    look = HighScore.Look(enter_initials=initials, award=award, music="high_score_bgm")
```

| Setting | Default | MPF |
|---|---|---|
| `categories` | `score`: GRAND CHAMPION, HIGH SCORE 1 to 4 | `categories` |
| `defaults` | VUK, ERY, PIN, BAL, LZZ | `defaults` |
| `enter_initials_seconds` | `20` | `enter_initials_timeout` |
| `award_seconds` | `4` | `award_slide_display_time` |
| `look` | vukery's two scenes, no music | `slide_player`, `sound_player` |

Overriding anything else (`mode_start`, say) is refused with a list of what
can change. To do more, react to its events in a mode of your own; or
replace it with a `high_score` mode of your own that isn't a subclass.

## Its scenes and events

Scenes read what it publishes (see [publishing values](scenes.md#values-from-modes)):

| Value | |
|---|---|
| `{high_score.player}` | the player entering initials |
| `{high_score.award}` | the award's label |
| `{high_score.initials}`, `{high_score.letter}` | the letters taken, and the one being chosen |
| `{high_score.name}`, `{high_score.value}` | the award being shown |
| `{high_score.score1_name}`, `…_value`, `…_label` | the tables, as MPF's machine variables (`score1` to `score5`, `multiball_score1`…) |

Events, with MPF's names: `high_score_enter_initials` (`player_num`,
`award`), `high_score_award_display` (`player_name`, `award`, `value`),
`high_score_complete`.

## Coming from MPF

| MPF | vukery |
|---|---|
| `high_score:` in the mode's config | settings on a subclass of `HighScore` |
| the `high_score` mode in `modes:` | `high_score` in `modes:` |
| machine variables `score1_name`… | `{high_score.score1_name}`… in scenes; `data/high_scores.yaml` |
| `text_input` widget, `high_score_enter_initials` slide | the `enter_initials` scene in its `look` |
