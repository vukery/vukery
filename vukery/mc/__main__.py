"""``python -m vukery.mc GAME_DIR [--display NAME] [--windowed] [--audio]``: one game's display windows.

``vuk us`` starts one of these per display, and the first one plays the
machine's sounds (``--audio``). A machine with sounds but no displays gets
one that only plays sound. Run it by hand to restart a display, or with
``--windowed`` to look at one at its configured size.
"""

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from vukery.core.config import load_game_config
    from vukery.core.errors import VukeryError
    from vukery.media import protocol

    parser = argparse.ArgumentParser(prog="python -m vukery.mc", description="vukery's media controller")
    parser.add_argument("game_dir", help="the machine folder")
    parser.add_argument("--display", help="the display to render (default: all of them)")
    parser.add_argument("--windowed", action="store_true", help="open windows at the displays' size, not full screen")
    parser.add_argument("--audio", action="store_true", help="play the machine's sounds too (with no displays: only that)")
    args = parser.parse_args(argv)
    try:
        config = load_game_config(Path(args.game_dir).resolve())
    except VukeryError as e:
        print(f"vukery.mc: {e}", file=sys.stderr)
        return 1
    displays = config.section("displays")
    if not displays and not args.audio:
        print("vukery.mc: this machine has no displays: section (use --audio to only play sound)", file=sys.stderr)
        return 1
    if args.display and args.display not in displays:
        print(f"vukery.mc: no display named {args.display!r} (displays: {', '.join(displays)})", file=sys.stderr)
        return 1
    try:
        from vukery.mc.app import run
    except ImportError:
        print("vukery.mc: the media controller needs pyglet (install vukery[mc])", file=sys.stderr)
        return 1
    port = int(config.section("media").get("port", protocol.DEFAULT_PORT))
    return run(port, {name: dict(entry or {}) for name, entry in displays.items()}, args.display, args.windowed,
               args.audio)


if __name__ == "__main__":
    sys.exit(main())
