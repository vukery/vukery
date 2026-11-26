# Coils

!!! note "0.0.x"
    Coils are built and tested on the FAST Nano (pulse, enable, timed
    enable, limits). Autofire coils and flippers come next.

Coils use the `coils:` section, with the same settings as MPF.

```yaml
coils:
  c_trough_eject:
    number: pf3208-4
    default_pulse_ms: 23
  c_ball_lock:
    number: pf3208-6
    default_hold_power: 0.25    # may be enabled (held on) at 25% power
  c_long_pulse:
    number: io1616-6
    max_hold_power: 1.0
    platform_settings:
      pwm2_ms: 2000             # FAST: hold up to 25.5 seconds
```

## Settings

| Setting | Default | Notes |
|---|---|---|
| `number` | (required) | The board and driver, e.g. `pf3208-4` |
| `default_pulse_ms` | `10` | |
| `default_pulse_power` | `1.0` | 0.0 to 1.0 |
| `max_pulse_ms` | the platform's maximum | |
| `max_pulse_power` | `1.0` | |
| `default_hold_power` | none | Power when the coil is enabled (held on). |
| `max_hold_power` | none | |
| `allow_enable` | `false` | Allow holding the coil on at full power |
| `default_timed_enable_ms` | `0` | How long a timed enable holds |
| `pulse_with_timed_enable` | `false` | Make every pulse a timed enable |
| `default_recycle` | none | FAST: use `platform_settings: recycle_ms` instead |
| `platform_settings` | | FAST: `recycle_ms`, `pwm2_ms` |

## Starting points by use

What to start from for each kind of coil. These are the typical values in 46
public MPF machine configs on GitHub (November 2026), thanks to everyone who
shares their machines. Each machine counts once, forks and copies are
counted once, and "most machines" is the middle half of them.

| Use | `default_pulse_ms` | Most machines | Hold | Machines |
|---|---|---|---|---|
| Flipper, single-wound (one coil pulses, then holds) | `25` | 20 to 35 | `default_hold_power: 0.125` (most: 0.1 to 0.25) | 6 |
| Flipper, dual-wound: the main (power) winding | `20` | 20 to 30 | none: the hold winding holds | 14 |
| Flipper, dual-wound: the hold winding | | | `allow_enable: true`, or `default_hold_power` 0.5 to 1.0 | 27 |
| Slingshot | `15` | 10 to 25 | | 26 |
| Pop bumper | `20` | 12 to 37 | | 21 |
| Trough eject | `20` | 16 to 30 | | 30 |
| Plunger or auto-launch | `20` | 18 to 38 | | 17 |
| Saucer, scoop or VUK eject | `25` | 20 to 34 | | 23 |
| Drop target bank reset | `35` | 24 to 68 | | 18 |
| Knocker | `40` | | | 5 |
| Chime or bell | `20` | | | 5 |
| Diverter | | | `default_hold_power: 0.5` (held while diverting) | 2 |

- **Treat them as a place to start, not an answer.** The right pulse depends
  on the coil, the voltage, the mech and how worn it is. Start at the low
  end, watch the shot, and raise it a few milliseconds at a time.
- **Keep hold power low.** Holding a coil at full power for long burns it.
  Single-wound flippers hold at about an eighth of full power.
- **Pop bumpers and slingshots** fire as hardware rules (`autofire_coils`),
  so the board fires them instantly; their pulse is the coil's
  `default_pulse_ms`.
- Dual-wound flippers aren't supported in vukery yet (see [Status](../status.md));
  their figures are here for when they are.

## Limits are enforced

vukery checks every pulse and enable before it reaches the hardware:

- **Power must be between 0.0 and 1.0**, and no higher than `max_pulse_power`
  (for pulses) or the coil's hold limit (for enables).
- **Pulse time must be between 0 and `max_pulse_ms`** (or the platform's
  maximum).
- **A coil can only be enabled (held on) if it has hold power:** a
  `default_hold_power`, a `max_hold_power`, or `allow_enable: true`.

A request outside these limits raises a `CoilLimitError` and the coil isn't
touched.

The hold power used when you don't give one follows MPF's order:
`default_hold_power`, then `max_hold_power`, then `1.0` if `allow_enable`,
otherwise none.
