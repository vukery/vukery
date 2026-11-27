# Ball saves

!!! note "0.0.x"
    MPF's `ball_saves:` device: timer, hurry-up, grace period, how many
    balls, only the last ball, eject delay. Specced with MPF's ball save
    scenarios. Early saves, delayed ejects and saving into ball locks come
    later.

A ball save gives a drained ball back for a while. As in MPF, it's a device:
a game can have several, each switched on by its own events.

```yaml
ball_saves:
  default:
    active_time: 10s
    hurry_up_time: 2s           # before the end: shoot again light blinks faster
    grace_period: 2s            # after the end: still saves, lights already off
    enable_events: mode_base_started
    timer_start_events: sw_playfield_active   # the clock starts once the ball's in play
    balls_to_save: 1
  pazuzu:
    active_time: 50s
    enable_events: start_pazuzu
    balls_to_save: 2
```

While it's on, a ball that drains is claimed before the game counts it, and
a new ball is served from the trough (to its `eject_targets`: the shooter
lane, say). A mode can also switch one on or off:

```python
self.machine.ball_saves["pazuzu"].enable()
```

## Settings

| Setting | Default | |
|---|---|---|
| `active_time` | `0` | seconds; `0` saves until it's disabled. MPF's `+15s` reads as 15 s |
| `hurry_up_time` | `0` | how long before the end the hurry-up starts |
| `grace_period` | `0` | how long after the end it still saves |
| `balls_to_save` | `1` | `-1`: any number |
| `only_last_ball` | `false` | only save the last ball in play (not during a multiball) |
| `eject_delay` | `0` | wait before serving the new ball |
| `enable_events` | none | |
| `timer_start_events` | none | start the clock on these instead of when enabled (can't also be in `enable_events`) |
| `disable_events` | `ball_will_end, service_mode_entered` | |
| `auto_launch` | `true` | accepted; the ball goes to the trough's eject target either way, for now |

Times take `10s`, `500ms` or a number: seconds for `active_time` (as MPF's),
milliseconds for the others (as MPF's).

## Events

| Event | |
|---|---|
| `ball_save_<name>_enabled` | |
| `ball_save_<name>_timer_start` | the clock started |
| `ball_save_<name>_hurry_up` | |
| `ball_save_<name>_grace_period` | |
| `ball_save_<name>_saving_ball` | `balls`, `early_save` |
| `ball_save_<name>_disabled` | |

Its look (a shoot again light show, a "shoot again" scene, a callout) is the
game's: react to these events in a mode. A tilted ball isn't saved: the
tilt ends the ball, which disables it first.

## Coming from MPF

The section, settings and events are MPF's. A ball save defined in a mode's
config in MPF goes in the machine config here; its `enable_events` (the
mode's started event, usually) still tie it to the mode, and it's disabled at
the end of each ball.
