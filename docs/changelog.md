# Changelog

vukery is in **0.0.x** while it works toward parity with MPF. Every push to
`main` bumps the last digit (0.0.1, 0.0.2, …) and is tagged (`v0.0.1`).
**0.1.0** will mark reasonable parity with MPF.

Check your version with `vuk --version`.

## 0.0.16 (2026-11-26)

- **Code coverage:** `uv run pytest --cov` measures how much of vukery the
  specs run (pytest-cov), branches included.
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
