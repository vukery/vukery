# Ball search

!!! note "0.0.x"
    MPF's ball search: the quiet timer, three phases of rounds, ball devices,
    autofire coils and a game's own devices taking part, giving up. Specced
    with MPF's ball search scenarios. Flippers, drop targets and other
    devices taking part come with those devices.

When the playfield goes quiet with a ball on it, the ball is probably stuck:
in a saucer that didn't kick, behind a slingshot, on a post. Ball search
fires the coils that might free it, gently at first. It's set up on the
playfield, with MPF's settings:

```yaml
playfields:
  playfield:
    enable_ball_search: true
    ball_search_timeout: 15s               # quiet this long, with a ball out: search
    ball_search_interval: 250ms            # between coils
    ball_search_wait_after_iteration: 10s  # between rounds
```

**Armed** while a ball is on the playfield: in play, and not waiting in a
plunger lane. Every playfield switch starts the timeout over (switches tagged
`playfield_active`, and the switches of autofire coils), and stops a search
that's running.

**Searching** goes through the devices that take part, in
`ball_search_order`, lowest first. After a device fires, it waits
`ball_search_interval`; after a whole round, `ball_search_wait_after_iteration`.
Rounds come in three phases, each firmer than the last:

| Device | Phase 1 | Phases 2 and 3 |
|---|---|---|
| ball device with an eject coil (order `200`) | pulses only if it's empty | pulses, except the trough |
| autofire coil (order `100`) | pulses | pulses |
| a game's own (`register`) | its choice | its choice |

A hit on an autofire coil's switch within 200 ms of ball search pulsing it is
the pulse, not the ball, so it doesn't stop the search.

**Giving up** after the last phase posts `ball_search_failed`, counts the
ball as lost, and does `ball_search_failed_action`:

| Action | |
|---|---|
| `new_ball` (default) | serve a new ball, and play on (if none is left, the game ends) |
| `end_ball` | end the ball |
| `end_game` | end the game |

If the lost ball turns up later, rolling into the trough, it's counted as
found, not as a drain. A game can start with fewer balls home by however
many are lost.

**While searching,** a game can't start (`ball_search_prevents_game_start`).
`flipper_cradle` blocks ball search and `flipper_cradle_release` unblocks
it (MPF's defaults); posting `cancel_ball_search` gives up now.

## Settings (`playfields: playfield:`)

| Setting | Default |
|---|---|
| `enable_ball_search` | `false` |
| `ball_search_timeout` | `15s` |
| `ball_search_interval` | `150ms` |
| `ball_search_wait_after_iteration` | `5s` |
| `ball_search_phase_1_searches`, `_2_`, `_3_` | `3`, `3`, `4` |
| `ball_search_failed_action` | `new_ball` |
| `ball_search_block_events`, `ball_search_unblock_events` | `flipper_cradle`, `flipper_cradle_release` |
| `ball_search_enable_events`, `ball_search_disable_events` | none |

A bare number is milliseconds, as in MPF. `tags` and `default_source_device`
are accepted. vukery has one playfield, named `playfield`.

On devices, `ball_search_order` (`ball_devices:`, `autofire_coils:`) sets the
order; `0` leaves a device out. A ball device tagged `no-eject-on-ballsearch`
is left out too.

## A game's own devices

Code that drives a coil itself (a kicker that isn't a ball device yet, say)
takes part with `register`:

```python
def search(phase, iteration):
    if phase == 1 and self.machine.switches["s_kicker"].state:
        return False                 # a ball's in it: it kicks by itself
    self.machine.coils["c_kicker"].pulse()
    return True                      # fired: wait before the next device

self.machine.ball_search.register(1, search, "kicker")
```

## Events

MPF's: `ball_search_started`, `ball_search_phase_1`, `_2`, `_3`
(`iteration`), `ball_search_stopped`, `ball_search_failed`,
`ball_search_prevents_game_start`.
