# Tilt

!!! note "0.0.x"
    Built: warnings, tilt, slam tilt, settling, the look. As MPF's `tilt`
    mode, and specced with MPF's tilt scenarios.

An optional [built-in mode](../index.md#built-in-modes). List it in `modes:`;
it runs all the time, even between games, so a slam tilt is always caught.

```yaml
modes:
  - base
  - tilt

switches:
  s_plumb_bob:
    number: 12
    tags: tilt_warning       # the plumb bob: warnings
  s_slam:
    number: 13
    tags: slam_tilt          # the slam switch on the coin door
```

**Warnings.** Each time the plumb bob closes, the player gets a warning, and
`tilt_warning_1`, `tilt_warning_2`… are posted. One nudge can swing the bob
several times, so it counts once within `multiple_hit_window`. Warnings go
back to zero at the end of each ball.

**Tilt.** The warning that reaches `warnings_to_tilt`, or a switch tagged
`tilt`, tilts the ball: `tilt` is posted, the ball ends at once, its modes
stop (no more scoring), and the flippers and slingshots go dead. The next
ball waits until every ball in play has drained and the bob has been still
for `settle_time`, then `tilt_clear` is posted. An extra ball is still
played.

**Slam tilt.** A switch tagged `slam_tilt` tilts too, posts `slam_tilt`, and
the game ends after that ball: no extra balls. Between games, it only posts
the event.

## Customizing it

```python
# modes/tilt/mode.py
from vukery.modes import Moment, Tilt

from .scenes import danger, danger_danger, tilted


class GrandPrixTilt(Tilt):
    settle_time = 5
    multiple_hit_window = 0.5
    look = Tilt.Look(
        warnings=(Moment(danger, 0.75, sound="tilt1"), Moment(danger_danger, 1.5, sound="tilt2")),
        tilt=Moment(tilted, sound="tilt3"),
    )
```

| Setting | Default | MPF |
|---|---|---|
| `warnings_to_tilt` | `3` | `warnings_to_tilt` |
| `multiple_hit_window` | `0.3` (seconds) | `multiple_hit_window` |
| `settle_time` | `5` (seconds) | `settle_time` |
| `reset_warnings_events` | `("ball_will_end",)` | `reset_warnings_events` |
| `tilt_warning_switch_tag`, `tilt_switch_tag`, `slam_tilt_switch_tag` | `tilt_warning`, `tilt`, `slam_tilt` | the same |
| `tilt_warnings_player_var` | `tilt_warnings` | the same |
| `look` | vukery's screens | `slide_player`, `sound_player` |

**The look** is a `Moment` for each warning in turn (the last one repeats)
and one for the tilt: a scene, how many seconds it stays (MPF's `expire`;
none: until the tilt clears), and a sound. For anything else at those
moments, such as blinking the backbox tilt light, react to `tilt_warning_1`,
`tilt` and the other events in a mode of your own.

## Events

| Event | |
|---|---|
| `tilt_warning` | `warnings`, `warnings_remaining` |
| `tilt_warning_1`, `tilt_warning_2`… | |
| `tilt` | the ball is tilted (`game.tilted` is true until it clears) |
| `slam_tilt` | (`game.slam_tilted` is true) |
| `tilt_clear` | the balls are in and the bob has settled |

## Coming from MPF

The `tilt:` settings become class attributes on a subclass, with MPF's names
and seconds instead of `500ms`. The `tilt_warning_1`, `tilt_warning_2` and
`tilt` slides become the `look`; `show_player` and `sound_player` entries on
the tilt events can go in the look (sounds) or a mode of your own.
