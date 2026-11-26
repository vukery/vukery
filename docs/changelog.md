# Changelog

vukery is in **0.0.x** while it works toward parity with MPF. Every push to
`main` bumps the last digit (0.0.1, 0.0.2, …) and is tagged (`v0.0.1`).
**0.1.0** will mark reasonable parity with MPF.

Check your version with `vuk --version`.

## 0.0.5 (2026-11-25)

The first numbered version. Everything built so far:

- **Game engine:**
  - events with MPF's ordering rules;
  - modes with priorities and MPF's lifecycle;
  - the async game loop (players, balls, turns, extra balls);
  - attract;
  - switches and player variables;
  - config with `development` / `test` / `production` environments.
- **Scoring:** `scoring` tables on modes (`Score`, `Award`, functions);
  MPF's per-variable scoring blocks; `BLOCK`; score adjusters for
  multipliers.
- **Devices:** coils with limits enforced in the engine; lights
  (MPF's channel numbering, colors, fades, RGBW); a simple trough;
  single-wound flippers; autofire coils.
- **Displays:** text slides with live player values on any number of
  displays, drawn by the pyglet media controller (one process per display)
  over vukery's JSON media protocol. The config decides whether a media
  controller loads.
- **Hardware:** the FAST Nano's NET and RGB ports, ported from MPF and
  tested against MPF's mock boards; port auto-detection. Not yet tried on a
  real machine.
- **Tools:** `vuk it`, `vuk mc` and `vuk doctor`; `VUK_ENV` and `VUK_LOG`;
  logging in MPF's format, one file per environment.
- **Testing:** RSpec-style specs on virtual time (`GameRig`, `expect`).
- **Examples:** `basic` (with a Frenzy mode for priority and blocking),
  `display`, and `dual_display`, each commented.
