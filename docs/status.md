# Status (0.0.x)

vukery is in early development. This page lists what exists today, so the
rest of the docs never describe something as if it already works.

| Piece | Status | Docs |
|---|---|---|
| `vuk` command | `vuk it`, `vuk me`, `vuk us` (development), `vuk you` and `vuk health` work; the others say they aren't built yet. | [The vuk command](cli.md) |
| Game engine | Built: MPF's event rules, modes, the game loop (players, balls, turns, extra balls), attract, switches, player variables, config with environments. Runs on the simulated platforms. | [Writing a game](writing-a-game.md) |
| Modes and scoring | Built: scoring tables (`Score`, `Award`, functions), MPF's per-variable scoring blocks, `BLOCK`, score adjusters (multipliers). | [Modes](modes.md) |
| Testing games | Built: RSpec-style specs on virtual time with `GameRig` and `expect`. | [Testing a game](testing.md) |
| Examples | `examples/basic` (no media), `examples/display` (one display) and `examples/dual_display` (two displays). | [Examples](examples.md) |
| Displays and scenes | Built: scenes of texts and nested scenes on any number of displays, full screen per monitor, scene priorities, entrances and exits, moves and blinks, live player values, the pyglet media controller, the media protocol (version 2). Images, sprite sheets, video and sound come later. | [Displays and scenes](scenes.md) |
| Shows | Built: YAML shows in a mode's folder, as a frames grid or MPF's steps; lights, coils and events; tokens; MPF's `show_player` options and built-in shows. Sounds, scenes and shows inside a show come later. | [Shows](shows.md) |
| Logging | Built and started by `vuk me` and `vuk us`: MPF's line format, one file per environment, per-component levels, `VUK_LOG`. | [Logging](logging.md) |
| FAST Nano: NET port | Built and tested against MPF's mock board: startup, switches, coils, hardware rules, firmware checks, reboot handling. Not yet tried on a real machine. | [FAST hardware](hardware/fast.md) |
| FAST Nano: RGB port | Built and tested: LEDs, colors, fades. | [FAST hardware](hardware/fast.md) |
| FAST port auto-detection | Built and tested (`port: auto`). | [FAST hardware](hardware/fast.md) |
| Coils | Built: MPF's settings, with limits enforced in the engine. | [Coils](devices/coils.md) |
| Troughs, flippers, autofire coils | First versions: a simple trough (count, eject, drain), a mechanical plunger lane (`eject_targets`, simulated as on smart_virtual), single-wound flippers, slingshots and pop bumpers. MPF's full ball device logic comes later. | [Writing a game](writing-a-game.md) |
| Lights | Built: MPF's channel numbering, colors, fades, RGBW, MPF's priority stack, light groups. | [Lights](devices/lights.md) |
| FAST Neuron and EXP boards | Planned, after COMBAT. | |
| Ball save, tilt, high score, match, other built-in modes | Planned. | |
| Sound | Built: sounds from `assets/sounds/`, MPF's `sounds:`, `sound_pools:` and tracks; `play_sound` with MPF's `sound_player` options; mixed with priorities, queueing, loops and ducking; played by `vuk me` and by `vuk us`. Fades, markers and sounds in shows come later. | [Sound](sound.md) |
| Images, video | Planned. | |
| `vuk me` dashboard | Built: a scrolling list of the game, switches, lights, coils and devices; the backbox, a pane per display, and the playfield; clicking switches; dragging switches and lights into the backbox or onto the playfield; resizable panes; all saved to `config/dashboard.yaml` (`arrangement_lock`). Never fires coils. Your own artwork comes later. | [The dashboard](dashboard.md) |

## What vukery is tested against

- **MPF's own tests.** vukery's FAST tests use MPF's mock FAST boards and read
  the expected serial traffic straight out of MPF's test files.
- **COMBAT**, the first game to move to vukery, which runs on a FAST Nano.
