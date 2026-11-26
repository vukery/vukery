# Status (0.0.x)

vukery is in early development. This page lists what exists today, so the
rest of the docs never describe something as if it already works.

| Piece | Status | Docs |
|---|---|---|
| `vuk` command | Skeleton. `vuk doctor` works; other commands say they aren't built yet. | [The vuk command](cli.md) |
| Logging | Built: MPF's line format, one file per environment, per-component levels, `VUK_LOG`. Not yet started by `vuk run`. | [Logging](logging.md) |
| FAST Nano: NET port | Built and tested against MPF's mock board: startup, switches, coils, hardware rules, firmware checks, reboot handling. Not yet tried on a real machine. | [FAST hardware](hardware/fast.md) |
| FAST Nano: RGB port | Built and tested: LEDs, colors, fades. | [FAST hardware](hardware/fast.md) |
| FAST port auto-detection | Built and tested (`port: auto`). | [FAST hardware](hardware/fast.md) |
| Coils | Built: MPF's settings, with limits enforced in the engine. | [Coils](devices/coils.md) |
| Lights | Built: MPF's channel numbering, colors, fades, RGBW. No priority stack yet. | [Lights](devices/lights.md) |
| FAST Neuron and EXP boards | Planned, after COMBAT. | |
| Game engine (modes, events, game flow) | Planned. | |
| Shows, slides, sounds, media controller | Planned. | |
| `vuk view` (playfield GUI) | Planned. | |

## What vukery is tested against

- **MPF's own tests.** vukery's FAST tests use MPF's mock FAST boards and read
  the expected serial traffic straight out of MPF's test files.
- **COMBAT**, the first game to move to vukery, which runs on a FAST Nano.
