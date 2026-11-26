"""The ``vuk`` command.

Commands mirror MPF's CLI where there's an equivalent (see each command's help),
with one verb per concept and options instead of combined command names.
"""

import argparse
import platform
import shutil
import sys
from collections.abc import Sequence

from vukery import __version__

ENVIRONMENTS = ("development", "test", "production")
DEFAULT_ENVIRONMENT = "development"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vuk",
        description="vukery: a very opinionated pinball framework based on the Mission Pinball Framework.",
        epilog="Environment variables: VUK_ENV picks the environment (development, test or production; "
               "default development; vuk test always uses test). VUK_LOG sets one log level for "
               "everything (debug, info, warning or error); per-component levels go in the logging: config.",
    )
    parser.add_argument("--version", action="version", version=f"vukery {__version__}")
    parser.add_argument("-C", dest="game_dir", metavar="DIR", default=".",
                        help="the game folder (default: the current folder)")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    run = commands.add_parser("run", help="run the game (MPF: mpf, mpf game, mpf both)")
    run.add_argument("--hardware", action="store_true", help="use real hardware in development")
    run.add_argument("--no-mc", action="store_true", help="don't start the media controllers")
    run.add_argument("--no-sound", action="store_true", help="run without audio")
    run.add_argument("--preload", action="store_true", help="load every asset at startup (MPF: -f)")
    run.add_argument("--log-dir", default="log", help="where log files go (default: log/)")

    mc = commands.add_parser("mc", help="run a media controller only (MPF: mpf mc)")
    mc.add_argument("--display", help="the display to render (default: all of them)")

    commands.add_parser("view", help="the playfield GUI: lights, switches, coils (MPF: mpf monitor)")
    commands.add_parser("top", help="terminal dashboard of a running game (MPF: mpf -t)")
    commands.add_parser("console", help="Python prompt attached to the running game (MPF: mpf service)")

    hardware = commands.add_parser("hardware", help="talk to the hardware directly (MPF: mpf hardware)")
    hardware.add_argument("action", choices=("scan", "switches", "lights", "coil"),
                          help="scan: boards and firmware; switches: live switch states; "
                               "lights: walk every LED; coil: pulse one coil (asks first)")
    hardware.add_argument("name", nargs="?", help="the coil to pulse (for: coil)")

    commands.add_parser("doctor", help="check the setup: versions, FFmpeg, serial ports (MPF: mpf diagnosis)")
    commands.add_parser("wire", help="FAST wiring instructions for the config (MPF: mpf wire)")

    test = commands.add_parser("test", help="run the game's specs in the test environment (MPF: mpf test)")
    test.add_argument("pytest_args", nargs=argparse.REMAINDER, help="passed to pytest")

    new = commands.add_parser("new", help="create a game folder (MPF: mpf create_config)")
    new.add_argument("name")

    generate = commands.add_parser("generate", help="create a mode, show or slide in a game (MPF: mpf create_config)")
    generate.add_argument("kind", choices=("mode", "show", "slide"))
    generate.add_argument("name")

    commands.add_parser("stubs", help="generate typed stubs from the machine config")
    return parser


def _doctor() -> int:
    print(f"vukery {__version__}")
    print(f"Python {platform.python_version()} ({sys.executable})")
    print(f"Platform {platform.platform()}")
    ffmpeg = shutil.which("ffmpeg")
    print(f"FFmpeg: {ffmpeg or 'not found (needed by the media controller)'}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    match args.command:
        case None:
            parser.print_help()
            return 0
        case "doctor":
            return _doctor()
        case command:
            print(f"vuk {command} isn't built yet.", file=sys.stderr)
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
