# Getting started

!!! note "0.0.x"
    vukery runs games on its simulated platforms today. Real hardware (the
    FAST Nano) is built but not yet tried on a machine. See
    [Status](status.md).

## What you need

- **[uv](https://docs.astral.sh/uv/)**. It installs Python 3.15 for you, so
  your system's Python doesn't matter.
- **FFmpeg**, for video and sound in the media controller
  (`brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Ubuntu).
- For FAST hardware: the controller connected over USB.

## Install the `vuk` command

```console
uv tool install "vukery[mc] @ git+https://github.com/vukery/vukery"
vuk doctor
```

`vuk doctor` prints the vukery, Python and platform versions, and whether
FFmpeg was found.

## Make a machine: `vuk it`

```console
vuk it my_machine
cd my_machine
uv sync            # installs vukery (pinned in pyproject.toml) and the test tools
uv run vuk me      # play it with the dashboard; Esc stops it
uv run vuk you     # run its specs
```

`vuk it` creates a complete, playable machine folder, much like `rails new`:

| Path | What's in it |
|---|---|
| `config/machine.yaml` | the machine: a trough, flippers, slingshots and a target, commented |
| `config/dashboard.yaml` | `vuk me`'s pane sizes and playfield positions |
| `config/environments/` | `development.yaml` (simulated) and `production.yaml` (where your hardware goes) |
| `modes/base/mode.py` | the base mode, with its scoring table |
| `modes/vukery/` | reserved for overrides of vukery itself |
| `assets/` | `sounds/`, `images/`, `videos/` and `fonts/` |
| `tests/` | specs for the whole game flow |
| `pyproject.toml` | vukery, pinned to the version that made the machine |

From there, change `config/machine.yaml` to match your machine and add
modes. See [Writing a game](writing-a-game.md), and the
[examples](examples.md) for more to copy.

The folder name is the machine's name: lowercase letters, digits, `-` and
`_`.
Run `vuk it` on its own and it asks for one.
`vuk it` won't write into a folder that already has files in it.

## Run commands through uv

Inside a machine folder, run vukery through `uv run`, so it uses the vukery
version the machine pins:

```console
uv run vuk me                       # play it on your computer
VUK_ENV=production uv run vuk us    # run it on the machine
uv run vuk you                      # its specs
```

If you use pyenv, plain `python` in the folder will complain that version
3.15 isn't installed. pyenv reads the `.python-version` file that uv uses,
but uv manages this Python, not pyenv. Use `uv run …`, or activate the
environment first (`source .venv/bin/activate`).

## Working on vukery itself

```console
git clone https://github.com/vukery/vukery.git
cd vukery
uv sync
uv run pytest
uv run pytest --cov             # the same, plus how much of vukery the specs cover
uv run mkdocs build --strict    # the docs site, into site/
```

`uv sync` installs the right Python, creates `.venv/` and installs vukery,
its development tools and MkDocs. Tests are written as RSpec-style specs
(`describe_…` / `it_…`) and print as a tree:

```text
Fast nano:
  Coils:
    ✓ It pulses
    ✓ It refuses pulse power above one
```
