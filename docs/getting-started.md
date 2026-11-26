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

`uv sync` installs the right Python, creates `.venv/` and installs vukery
and its development tools.

## Check your setup

```console
uv run vuk doctor
```

`vuk doctor` prints the vukery, Python and platform versions, and whether
FFmpeg was found.

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
