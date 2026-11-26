# Getting started

!!! note "0.0.x"
    vukery can't run a game yet. These steps install it and check your
    setup. See [Status](status.md) for what works.

## What you need

- **Python 3.15**, the latest stable release. [uv](https://docs.astral.sh/uv/)
  installs it for you, so your system's Python doesn't matter.
- **FFmpeg**, for video and sound in the media controller
  (`brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Ubuntu).
- For FAST hardware: the controller connected over USB.

## Install

```console
git clone https://github.com/vukery/vukery.git
cd vukery
uv sync
```

`uv sync` installs the right Python, creates `.venv/` and installs vukery,
its development tools and MkDocs.

## Check your setup

```console
uv run vuk doctor
```

`vuk doctor` prints the vukery, Python and platform versions, and whether
FFmpeg was found.

## Run commands through uv

Run vukery's tools with `uv run`, so they use the project's Python and
packages in `.venv/`:

```console
uv run vuk doctor
uv run pytest
uv run mkdocs build --strict    # the docs site, into site/
```

If you use pyenv, plain `mkdocs` or `python` in this folder will complain
that version 3.15 isn't installed. pyenv reads the `.python-version` file
that uv uses, but uv manages this Python, not pyenv. Use `uv run …`, or
activate the environment first (`source .venv/bin/activate`).

## Run the tests

```console
uv run pytest
```

Tests are written as RSpec-style specs (`describe_…` / `it_…`) and print as
a tree:

```text
Fast nano:
  Coils:
    ✓ It pulses
    ✓ It refuses pulse power above one
```
