# Changelog

vukery is in **0.0.x** while it works toward parity with MPF. Every push to
`main` bumps the last digit (0.0.1, 0.0.2, …) and is tagged (`v0.0.1`).
**0.1.0** will mark reasonable parity with MPF.

Check your version with `vuk --version`.

## 0.0.30 (2026-11-27)

- **Docs site:** the whole menu stays open from page to page, pages show
  breadcrumbs and load in place, and the pages that moved in 0.0.29 redirect
  to their new places.

## 0.0.29 (2026-11-27)

- **Ball search**, MPF's: when the playfield goes quiet with a ball on it,
  ball devices, slingshots and bumpers, and a game's own devices fire in
  order, in three phases; then it gives up with a new ball (or ends the ball
  or game). Lost balls that turn up later are found, not drained. Set up in
  `playfields: playfield:`. See [Ball search](devices/ball-search.md).
- `game.end_game()`.
- **Strict types and lint, checked in CI:** pyright (strict) and ruff now run
  on every push, on all of vukery except the files copied from MPF. Specs,
  types and lint are separate workflows, each with a badge in the README.
- **The docs are reorganized:** seven sections instead of seventeen pages,
  with built-in modes under Modes and devices and hardware under Machine.

## 0.0.28 (2026-11-26)

- **Ball saves**, MPF's `ball_saves:` device: as many as a game needs, each
  enabled by its events or from a mode, with its clock, hurry-up, grace
  period, how many balls, only the last ball, and eject delay. See
  [Ball saves](devices/ball-saves.md).
- **MPF's color names** (the web's: `orange`, `red`, `off`…) work wherever a
  color does, so MPF shows that use them carry over.

## 0.0.27 (2026-11-26)

- **Tilt** (MPF's `tilt`), an optional built-in mode: plumb bob warnings,
  tilt, slam tilt, waiting for the balls and the bob to settle. Its look is
  a scene, how long it stays and a sound for each warning and for the tilt.
  See [Tilt](modes/built-in/tilt.md).
- **A ball's modes stop inside `ball_ending`**, as in MPF: earlier than
  before, so handlers that wait on `ball_ending` (tilt) run with them
  stopped.
- `game.tilted` and `game.slam_tilted`, and ball devices post MPF's
  `balldevice_<name>_ball_enter`.

## 0.0.26 (2026-11-26)

- **Dual-wound flippers and EOS switches**, as MPF's: `hold_coil`,
  `eos_switch`, `use_eos`, `repulse_on_eos_open`. Each kind of flipper sets
  MPF's hardware rules (on FAST, driver modes 18, 75 and 20). `vuk me` shows
  which coils the rules hold on. See [Flippers](devices/flippers.md).

## 0.0.25 (2026-11-26)

- **Fixed:** specs wrote high score tables into the machine's `data/`
  folder, so one run changed the next. The spec rig now keeps a machine's
  data in a temporary folder (`GameRig(data_dir=...)` to choose).

## 0.0.24 (2026-11-26)

- **Built-in modes are sealed.** A game customizes one with a subclass that
  changes only what the mode declares (settings, look, hooks); anything else
  is refused with a list of what can change. Optional built-ins can be
  replaced by a game's own mode of the same name; core ones (attract, game)
  can't. See [Modes](modes/index.md#built-in-modes).
- **High score** (MPF's `high_score`), the first optional built-in: list it
  in `modes:`. Initials with the flippers and start, the award screens, and
  tables saved in `data/high_scores.yaml`. See [High score](modes/built-in/high-score.md).
- **`use_wait_queue`** (MPF's): a mode started by a queue event such as
  `game_ending` holds it until the mode stops.
- **Values from modes:** `self.publish(countdown=10)` is `{frenzy.countdown}`
  in a scene.
- New matcher: `expect(x).to_be(y)`, the same object.
- The examples and new machines tag their flipper buttons (`left_flipper`,
  `right_flipper`), and new machines keep `data/` out of git.

## 0.0.23 (2026-11-26)

- **Keys in `vuk me`:** MPF's `keyboard:` section, so an MPF machine's
  carries over. A key holds a switch (`toggle`, `invert`) or posts an event
  with `params`, with `ctrl+`, `shift+` and `alt+` combinations. Simulated
  platforms only, as clicks. `examples/basic` and new machines from `vuk it`
  have start, flipper and trough keys. See [the dashboard](tools/dashboard.md#keys).
- **Your own playfield and backbox in `vuk me`:** put `playfield.jpg` or
  `backbox.png` (or both) in the machine's `assets/images/`, and `vuk me`
  draws them instead of the wooden ones. An MPF machine's Monitor playfield
  lines up with its migrated positions. See
  [the dashboard](tools/dashboard.md#your-own-playfield-and-backbox).
- **Fixed:** files a machine started from its own folder (`.`) passed to
  media controllers were relative paths; the machine folder is now made
  absolute when the config loads.

## 0.0.22 (2026-11-26)

- **Fixed:** sounds that started before a media controller connected were
  never heard: the attract music, which starts at power-on, before `vuk me`'s
  dashboard or `vuk us`'s displays connect. A media controller that connects
  late now picks up what's playing, from where it is.
- **Fixed:** `.ogg`, `.mp3` and other sounds played in silence. pyglet's
  FFmpeg binding returned no audio with FFmpeg 8.1 on macOS, so vukery now
  decodes every sound but `.wav` with the `ffmpeg` command: short sounds
  once, into memory, and music as it plays. `vuk health` checks for the
  command.

## 0.0.21 (2026-11-26)

- **Sound.** Every file in `assets/sounds/` is a sound; MPF's `sounds:`,
  `sound_pools:` and `sound_system: tracks:` give them settings, so an MPF
  machine's sound config carries over. Modes `play_sound(...)` with MPF's
  `sound_player` options (`volume`, `loops`, `priority`, `start_at`, `delay`,
  `max_queue_time`) and `stop_sound(...)`. The media controller mixes as MPF
  does: track limits, priorities, queueing, loops and ducking. `vuk me` plays
  sound, and so does the first display's media controller in `vuk us`. See
  [Sound](media/sound.md).
- **Specs:** `expect(game).to_have_played("name")`, `game.sounds()`. The
  rig now listens from power-on.
- `examples/display` beeps when its target is hit.

## 0.0.20 (2026-11-26)

- **Scenes are clipped to their display:** an actor moving past the edge is
  cut off there, in `vuk me`'s display panes too.
- **Any player's values:** `{players[2].score:,}` (MPF: `(player2|score)`),
  empty until that player exists.
- **Fixed:** `vuk me` clipped its scrolling list with the wrong scale on
  HiDPI screens.
- **Plunger lanes:** a ball device with `mechanical_eject: true`, and
  `eject_targets:` on the trough. On the simulated platforms an eject moves
  the ball into its target, as on MPF's smart_virtual platform: after
  pressing start, the ball sits in the shooter lane until you shoot it
  (click its switch in `vuk me`). Balls start only in troughs, and only a
  device tagged `drain` reports drains.

## 0.0.19 (2026-11-26)

- **Actors move and blink.** `.moves(x=, y=, seconds=, repeat=, back=)` moves
  any actor from where it's placed to another point: once, there and back,
  or over and over (a scroll). `.blinks(every=, times=, fade=)` turns it off
  and on, or fades it out and in (MPF's pulsate). See
  [Displays and scenes](media/scenes.md#animations-moves-and-blinks).
- `game.screen()` lists only what's visible at that moment.
- The display examples blink, fade and move.

## 0.0.18 (2026-11-26)

- **Shows:** YAML files in their mode's folder, played with
  `self.play_show(...)` and MPF's `show_player` options. Write one as a
  frames grid over a light group, or as MPF's list of steps (lights, coils,
  events, fades). Tokens, loops, speed, keys, pause and resume, and MPF's
  built-in shows. See [Shows](media/shows.md).
- **The light stack:** each light shows its highest-priority color, as in
  MPF. Shows borrow lights and give them back when they stop; a mode's shows
  stop with the mode.
- **Light groups:** `light_groups:` in `machine.yaml`, ordered lists of
  lights that work like a light.
- **Scenes replace slides:** a `Scene` holds actors (`Text`, or another
  scene placed inside it). Actors can `.enters(side)` and `.exits(side)`.
  Scenes are `@scene` functions in a mode's `scenes.py`, shown with
  `self.show_scene(...)`. The media protocol is now version 2. See
  [Displays and scenes](media/scenes.md).
- **Coil starting points:** the [Coils](devices/coils.md) page has typical
  settings for each kind of coil, from 46 public MPF machines.
- **Indented YAML:** examples, the machine template and the docs write one
  setting per line, with bare hardware numbers (`number: 1`). Coils read a
  bare number as text, as switches and lights already did. `vuk me` writes
  pane sizes the same way.
- **`vuk doctor` is now `vuk health`.** It reports the version that's
  actually running (editable installs included), where vukery was installed
  from, pyglet, and whether pyglet found FFmpeg's libraries.
- **Specs** use `expect(...)` everywhere; new matchers: `not_to_equal`,
  `to_be_true` / `to_be_false`, `to_be_none`, `to_contain`,
  `to_be_close_to`, `to_be_greater_than` / `to_be_less_than`.

## 0.0.17 (2026-11-26)

- **Coverage from 74% to 83%:** 78 new specs.
  - **FAST Nano:** MPF's single-wound and dual-wound flipper rule
    scenarios (the exact serial commands), an RGB processor reboot, and the
    messages for switch and driver numbers that don't exist.
  - **Switches held down** (`@on.switch(..., hold=2)`), including across
    balls, plus `events_when_activated` / `deactivated`.
  - Light channel orders, `previous`, RGBW and fades; coil limits; extra
    balls and `player_vars:`; environment folders; and the error messages
    for config, machine, slides and scoring mistakes.
  - The FAST EXP board code isn't counted until EXP support is built: nothing
    can run it yet.
- **Fixed:** `vuk you <test path>` measured the tests instead of the code (a
  bare `--cov` took the path as its value).
- **Fixed:** a machine that failed while setting up left its event loop open.

## 0.0.16 (2026-11-26)

- **Code coverage:** `vuk you` measures how much code the specs run
  (pytest-cov, branches included): a machine's `modes/`, or vukery itself
  when run in vukery. `--no-cov` turns it off. New machines get pytest-cov.
- **`vuk you` is how vukery's own suite runs too** (`uv run vuk you`, here
  and in CI).
- **CI:** every push and pull request runs the specs with coverage on GitHub
  Actions. On `main` it redraws the coverage badge at the top of the README,
  kept on the `badges` branch, with no outside service.

## 0.0.15 (2026-11-26)

- **A mode is a folder, and its main file is `mode.py`:** `modes/<name>/mode.py`.
  Rename `modes/<name>/<name>.py` to `mode.py`; vukery tells you which.
- **Every folder in `modes/` needs a `mode.py`:** vukery checks when the
  machine starts (`modes/vukery/` excepted).
- **Split a mode into files:** `mode.py` keeps the class and what
  configures it (settings, scoring table); bigger parts go next to it
  (`slides.py`, helper code), imported with `from .slides import SLIDES`.
  That's the recommended layout; one file still works.
- `examples/display`, `examples/dual_display` and new machines from `vuk it`
  use split files; `examples/basic` stays in one file per mode.
- `config/dashboard.yaml`'s positions are where each light and switch
  physically sits.

## 0.0.14 (2026-11-25)

- **The dashboard's list is in two columns,** with 1.5× larger text. The
  list can be dragged to at most half the window.
- **The playfield sizes itself:** as wide as its 1:2 shape needs, at most a
  third of the window. The backbox and displays take the rest.
  `dashboard.yaml` now stores the list's width and the middle panes'
  heights (older files still load).
- **New playfield art** with flippers and an apron; a flipper is drawn
  raised over it while its coil is on.

## 0.0.13 (2026-11-25)

- **A simpler `vuk me` dashboard:**
  - one **list** pane (40%, full height) with the game, switches, lights,
    coils and devices, in fixed-size text, with a scrollbar;
  - a **backbox** pane, a pane for **each display**, and the **playfield**.
- **Place switches and lights** by dragging them from the list into the
  backbox or onto the playfield; drag them back to take them off. Positions
  are fractions of the pane, so they follow it when it's resized.
  Unplaced items no longer appear on the playfield.
- **A quick click taps a switch;** holding presses it. Dragging never
  presses one.
- **The backbox stays square and the playfield 1:2,** however their panes
  are sized; placed items stay put.
- **The dashboard opens as a resizable 1280×800 window.**
- `config/dashboard.yaml` has the new panes (`list`, `backbox`, one per
  display, `playfield`) and `backbox:` positions. `arrangement_lock` also
  stops placing.

## 0.0.12 (2026-11-25)

- **No more `vuk mc`.** `vuk us` starts each display's window itself
  (`python -m vukery.mc`), and `vuk me` draws the displays in its backbox.
  To restart a display or look at one in a window:
  `uv run python -m vukery.mc . --display main --windowed`.

## 0.0.11 (2026-11-25)

- **Resizable `vuk me` panes:** drag the edge between two panes. Letting go
  saves every pane's size, as a % of the window to the nearest tenth, to
  `config/dashboard.yaml`. `arrangement_lock: true` stops resizing.
- **`config/dashboard.yaml`** holds the dashboard's settings, including the
  playfield positions that were in `machine.yaml`. `vuk it` creates it.
- **Larger text on the dashboard,** growing with the window.
- **Wood backbox and playfield backgrounds,** with the displays and
  playfield items drawn on top.
- Ball device switches share one label on the playfield.

## 0.0.10 (2026-11-25)

- **`vuk you` runs a machine's specs** with pytest, always in the test
  environment. Extra arguments go to pytest (`vuk you -k scoring`).
  `vuk test` is an alias.
- New machines, the examples and the docs use `uv run vuk you`.

## 0.0.9 (2026-11-25)

- **`vuk it NAME` creates a machine folder,** much like `rails new`. You get:
  - a commented machine config, with development and production
    environments;
  - a base mode and specs for the whole game flow;
  - asset folders and `modes/vukery/`;
  - a `pyproject.toml` that pins vukery.

  Leave out the name and it asks. It replaces the planned `vuk new`.
- **`vuk us` runs a machine** (it was `vuk it`): the game and its displays,
  full screen.
- **Getting started** now walks through installing `vuk` and making a
  machine.

## 0.0.8 (2026-11-25)

- **`vuk me`:** play a game on your computer with a full-screen dashboard
  in three columns:
  - switches, lights, coils and other devices;
  - a virtual backbox with the game's displays, over the game and its
    running modes;
  - a virtual playfield to click.

  Positions go in a new `dashboard: playfield:` config section. The
  dashboard can never fire a coil. It replaces the planned `vuk view`.
- **`vuk it` is how a machine runs:** displays open full screen, each on
  its own monitor (`screen:` picks one). `vuk mc --windowed` opens a
  display at its configured size.
- **The examples page links to every example** on GitHub, ready to copy.
- `examples/basic` gets a light, lit while Frenzy runs.

## 0.0.7 (2026-11-25)

- **Every earlier push now has a version and a tag** (v0.0.1 to v0.0.6),
  as if vukery had been versioned from the start. The planning commits are
  squashed into one. Code is unchanged.
- **The README says who vukery is for:** developers who don't mind writing
  a little Python, and tech-savvy LLM users.

## 0.0.6 (2026-11-25)

- **The README opens with "Get VUKed!":** an AI-assisted total vukery of a
  pinball framework with a different mission. Its status line now reflects
  what's built.
- **Contributing:** vukery is an AI-driven project. Pull requests are
  welcome but will probably not be merged; issues are welcome; forking is
  encouraged ("vuk yourself"). The policy is in `CONTRIBUTING.md` and on
  the docs site.

## 0.0.5 (2026-11-25)

- **Versioning:** the version lives only in `pyproject.toml`, and
  `vuk --version` prints it. Every push to `main` bumps the last digit and
  is tagged.
- **This changelog.**

## 0.0.4 (2026-11-25)

- **Scoring:** `scoring` tables on modes (`Score`, `Award`, functions);
  MPF's per-variable scoring blocks; `BLOCK`; score adjusters for
  multipliers.
- **A Modes page** in the docs: priority, scoring, blocking and adjusters.
- **Examples:** `basic` gets a Frenzy mode for priority and blocking, and
  every example is commented for game makers.

## 0.0.3 (2026-11-25)

- **Game engine:**
  - events with MPF's ordering rules;
  - modes with priorities and MPF's lifecycle;
  - the async game loop (players, balls, turns, extra balls);
  - attract;
  - switches and player variables;
  - config with `development` / `test` / `production` environments;
  - the simulated `development` and `test` platforms, a simple trough,
    single-wound flippers and autofire coils.
- **Displays:** text slides with live player values on any number of
  displays, drawn by the pyglet media controller (one process per display)
  over vukery's JSON media protocol. The config decides whether a media
  controller loads.
- **Tools:** `vuk it` runs a game from its folder; `vuk mc`.
- **Testing:** RSpec-style specs on virtual time (`GameRig`, `expect`).
- **Examples:** `basic`, `display` and `dual_display`.
- MkDocs installs by default; tools run through `uv`.

## 0.0.2 (2026-11-25)

- **Hardware:** the FAST Nano's NET and RGB ports, ported from MPF and
  tested against MPF's mock boards; port auto-detection. Not yet tried on a
  real machine.
- **Devices:** coils with limits enforced in the engine; lights (MPF's
  channel numbering, colors, fades, RGBW).
- **Logging** in MPF's format, one file per environment, with dotted
  component names; `VUK_ENV` and `VUK_LOG`.
- **The `vuk` command,** with `vuk doctor`.
- **The first user docs.**

## 0.0.1 (2026-11-23)

- **The plan:** the repo, license, project conventions, the MPF import
  script (pinned to MPF 0.57.x), the pyglet media controller choice,
  Python 3.15, and RSpec-style test tooling.
