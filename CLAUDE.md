# vukery: notes for agents

vukery is a very opinionated pinball framework based on the Mission Pinball
Framework (MPF) 0.57 (the 0.57.x branch), built to be simple, lean and LLM-friendly.

**Docs live in two places:**
- **`docs/`** holds the user-facing docs, which are committed and published
  to vukery.com. `README.md` is a symlink to `docs/index.md`.
- **`notes/`** holds the build notes, which are **git-ignored**:
  `notes/PLAN.md` (what we're building and in what order) and
  `notes/DECISIONS.md` (every decision, with why and what it costs). They
  may not exist in your checkout.

  Never move build notes into `docs/`, and never link to `notes/` from a
  committed file.

When a decision conflicts with your instincts, the decision wins. If you
think one is wrong, say so instead of working around it.

## Hard rules

- **Nothing but praise for MPF and the Mission Pinball team.** vukery is
  an opinionated departure, never a criticism. In docs, comments, commit
  messages and anything public, describe what vukery does ("vukery checks
  the firmware minimum"), never what MPF gets wrong. "Coming from MPF"
  sections map names and concepts; they don't compare quality.

- **Never depend on the `mpf` package.** Don't install, import or vendor
  it. Copying individual MPF files is fine, but only with
  `scripts/import_mpf.py`:
  - it fetches from GitHub at the pinned commit
    `9ef886f4f263db44704f09a87bfd11229036ab5c` (0.57.x head, 0.57.6);
  - it adds a permalink header and an entry in `vukery/_mpf/NOTICE`;
  - it commits the verbatim copy on its own.

  Change the copied code only in later commits. Never hand-copy MPF code,
  and never copy from a local `site-packages`.
- **No game logic in YAML.** YAML describes the machine: hardware,
  devices, settings, asset settings, the vuk view layout. Conditions,
  shows and slides are Python.
- **No `CustomCode`.** Anything that hooks into the machine is a `Mode`,
  named for what it does (`HoleScore`, not `Custom`). Always-on code uses
  `game_mode = False`. Customize a built-in mode by subclassing it.
- **No Godot, no MPF 0.8x, no BCP.** Media controllers use vukery's own
  JSON media protocol. The default media controller uses pyglet, and the
  engine never imports any media library.
- **The CLI is `vuk`.** Environment variables, not flags, set the
  environment and logging: `VUK_ENV` (default `development`) and `VUK_LOG`
  (e.g. `VUK_LOG=info,fast=debug,fast.rgb=off`). Components log under dotted
  names through `vukery.core.log`, never a private debug flag.
- **Environments are enforced in code:**
  - `test` never opens serial ports or touches hardware;
  - `development` needs `--hardware` to touch hardware;
  - `production` refuses to start without coil limits and the watchdog;
  - the simulated platforms are named `development` and `test`, never
    "virtual" or "smart_virtual";
  - game code never branches on the environment.
- **Coil safety isn't optional.** Pulse and hold limits are enforced in
  the engine, and `vuk view` can never fire a coil.

## Conventions

- Python 3.15. Use `uv`, `ruff`, `pyright` in strict mode,
  and `pytest`.
- **Prefer `match` / `case` over chains of `if` / `elif` / `else`** wherever
  it fits: dispatching on values, types, config shapes or message headers.
  Plain `if` is fine for a single condition or guard. Code copied from MPF
  stays close to the original until it's properly reworked, so its diffs
  against the import commit stay readable.
- **Keep MPF's names wherever there's an equivalent:** events
  (`ball_started`, `mode_<name>_started`, `<switch>_active`), hardware YAML
  keys and device fields. That's what makes MPF games easy to migrate with
  an LLM.
- **One method per concept, with options. Never combined helper names.**
  Tests use pytest with pytest-describe (`describe_` / `context_` /
  `it_`):
  - `game.switch("s_hole")` (with options `state=`, `hold=`, `times=`,
    `every=`) replaces MPF's `hit_and_release_switch` family;
  - `game.advance(seconds)` is always a separate, consecutive call;
  - assertions are `expect(...)` matchers named after MPF's assertions
    (`expect(game.mode("base")).to_be_running()`).
- **Game folder layout:**
  - `config/`, with `config/environments/<env>` deep-merged over the
    shared files;
  - `modes/`, with `modes/vukery/` reserved for game-specific overrides
    and monkey patches;
  - `assets/{sounds,images,videos,fonts}/`, where assets are named by file
    name without the extension.
- **Modular:** build one implementation, but keep a clean plug-in
  boundary (entry points) for media controllers, platforms and mode
  libraries.
- **Lean:** don't add features no current game needs. Check the non-goals
  in `notes/PLAN.md` before expanding scope.
- **Record new decisions** in `notes/DECISIONS.md`, newest first, with what
  was decided, why, and what it costs.
- **User-facing docs** (how to use vukery, `MIGRATING.md`,
  `MEDIA_PROTOCOL.md`, `SEMANTICS.md`) go in `docs/` and must build with
  `mkdocs build --strict`.

## Reference material

- MPF 0.57.x on GitHub at the pinned commit is the reference for the
  rewrite. MPF's tests list the behaviors to cover.
- The first target game is COMBAT (`../combat`, FAST Nano). Its vukery
  version lives on that repo's `vukery` branch. Grand Prix
  (`../grand-prix`) and Fallout (`../fallout`) come later.
