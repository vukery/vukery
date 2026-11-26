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
