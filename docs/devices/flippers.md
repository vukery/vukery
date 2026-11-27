# Flippers

!!! note "0.0.x"
    Single- and dual-wound flippers, with or without an EOS switch, as MPF's.
    Specced against MPF's flipper tests and FAST's commands; not yet tried on
    a real machine. Flipping from code (`sw_flip_events`), power settings and
    ball search come later.

Flippers use MPF's `flippers:` section. The controller drives them itself,
through hardware rules, the moment the button closes: vukery only switches
the rules on (at `ball_started`) and off (at `ball_will_end` and
`service_mode_entered`), MPF's defaults.

```yaml
flippers:
  left_flipper:
    main_coil: c_flipper_main_1      # the power winding
    hold_coil: c_flipper_hold_1      # the hold winding: dual-wound
    activation_switch: s_flipper_1   # the cabinet button
    eos_switch: s_flipper_1_eos      # end of stroke
    use_eos: true
```

## What each kind does

| Flipper | Main coil | Hold coil |
|---|---|---|
| single-wound | pulses, then holds, until the button opens | |
| dual-wound | pulses until the button opens | pulses, then holds, until the button opens |
| dual-wound, `use_eos` | pulses until the button opens or EOS closes | pulses, then holds, until it opens |
| single-wound, `use_eos` | pulses, then holds; EOS closing cuts it to hold | |

Each coil fires with its own settings from `coils:` (`default_pulse_ms`,
`default_hold_power`), within its [limits](coils.md#limits-are-enforced). A
hold coil must be allowed to stay on: give it `default_hold_power`,
`max_hold_power` or `allow_enable: true`, or vukery stops with an error.

## Settings

| Setting | Default | |
|---|---|---|
| `main_coil` | (required) | |
| `hold_coil` | none | a dual-wound flipper's hold winding |
| `activation_switch` | (required) | the button |
| `eos_switch` | none | the end-of-stroke switch |
| `use_eos` | `false` | cut the main coil (or drop a single-wound coil to hold) when EOS closes |
| `repulse_on_eos_open` | `false` | pulse again if EOS opens while the button is held (the ball knocked it down) |
| `eos_active_ms_before_repulse` | `500` | |
| `enable_events` | `ball_started` | |
| `disable_events` | `ball_will_end, service_mode_entered` | |
| `label` | the name | |

`main_coil_overwrite`, `hold_coil_overwrite`, `power_setting_name`,
`sw_flip_events`, `sw_release_events` and the ball search settings aren't
supported yet; vukery says so if a config has them.

## In `vuk me`

The dashboard shows which coils the rules are driving: while the button is
held, the hold coil, and the main coil until EOS closes. On the simulated
platforms nothing moves the EOS switch by itself; press it to see the cut.

## Coming from MPF

The section, settings and rules are MPF's, so an MPF machine's `flippers:`
carries over. On FAST hardware the rules are FAST's driver modes 18 (pulse
and hold), 75 (pulse, cut by EOS) and 20 (pulse and hold, EOS drops to hold),
sent with MPF's own FAST code.
