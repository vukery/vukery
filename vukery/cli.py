"""The ``vuk`` command.

Commands mirror MPF's CLI where there's an equivalent (see each command's help),
with one verb per concept and options instead of combined command names.
"""

import argparse
import platform
import shutil
import subprocess
import sys
from collections.abc import Sequence
from typing import Any

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

    run = commands.add_parser("it", help="run the game in this folder (MPF: mpf, mpf game, mpf both)")
    run.add_argument("--hardware", action="store_true", help="use real hardware in development")
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


def _run(args: argparse.Namespace) -> int:
    """Run the game in the game folder until Ctrl-C (or "quit")."""
    import asyncio
    import os
    from pathlib import Path

    from vukery.core.config import load_game_config
    from vukery.core.errors import VukeryError
    from vukery.core.log import LoggingConfig, setup_logging
    from vukery.core.machine import Machine

    game_dir = Path(args.game_dir).resolve()
    try:
        config = load_game_config(game_dir)
        logging_config = LoggingConfig.from_yaml(config.section("logging")).with_vuk_log(os.environ.get("VUK_LOG"))
        log_dir = None if config.environment == "test" else game_dir / args.log_dir
        setup_logging(logging_config, config.environment, log_dir)
        machine = Machine(config, hardware=args.hardware)
    except VukeryError as e:
        print(f"vuk it: {e}", file=sys.stderr)
        return 1

    loop = machine.loop
    asyncio.set_event_loop(loop)

    async def type_switches() -> None:
        """development: type a switch name and press Enter to tap it ("quit" to stop)."""
        reader = asyncio.StreamReader()
        await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
        while line := (await reader.readline()).decode().strip():
            match line:
                case "quit" | "exit":
                    break
                case name if name in machine.switches.switches:
                    machine.set_switch(name, 1)
                    machine.clock.call_later(0.05, machine.set_switch, name, 0)
                case other:
                    print(f"No switch named {other!r}. Switches: {', '.join(machine.switches.switches)}")
        machine.stop("quit")

    media_controllers: list[Any] = []
    try:
        loop.run_until_complete(machine.start())
        print(f"vukery is running {game_dir.name} ({config.environment}). Ctrl-C to stop.")
        if machine.media is not None:  # the config decides: displays: means media controllers
            media_controllers = _start_media_controllers(game_dir, list(machine.media.displays))
        if config.platform == "development":
            if sys.stdin.isatty():
                print("Type a switch name and press Enter to tap it, e.g. s_start.")
            loop.run_until_complete(type_switches())
        else:
            loop.run_forever()
    except KeyboardInterrupt:
        machine.stop("Ctrl-C")
    except VukeryError as e:
        print(f"vuk it: {e}", file=sys.stderr)
        return 1
    finally:
        _shut_down(loop)
        for process in media_controllers:
            try:
                process.wait(timeout=2)  # they exit on the engine's "bye"
            except subprocess.TimeoutExpired:
                process.terminate()
        loop.close()
    return 0


def _shut_down(loop: Any) -> None:
    """Let final messages go out, then cancel whatever is still running."""
    import asyncio

    if loop.is_closed():
        return
    loop.run_until_complete(asyncio.sleep(0.1))
    pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))


def _start_media_controllers(game_dir: Any, displays: list[str]) -> list[Any]:
    """One media controller process per display (they exit when the engine says bye)."""
    return [subprocess.Popen([sys.executable, "-m", "vukery.cli", "-C", str(game_dir), "mc", "--display", name])
            for name in displays]


def _mc(args: argparse.Namespace) -> int:
    """Run a media controller for the game in the game folder."""
    from pathlib import Path

    from vukery.core.config import load_game_config
    from vukery.core.errors import VukeryError
    from vukery.media import protocol

    try:
        config = load_game_config(Path(args.game_dir).resolve())
    except VukeryError as e:
        print(f"vuk mc: {e}", file=sys.stderr)
        return 1
    displays = config.section("displays")
    if not displays:
        print("vuk mc: this game has no displays: section", file=sys.stderr)
        return 1
    if args.display and args.display not in displays:
        print(f"vuk mc: no display named {args.display!r} (displays: {', '.join(displays)})", file=sys.stderr)
        return 1
    try:
        from vukery.mc.app import run
    except ImportError:
        print("vuk mc: the media controller needs pyglet (install vukery[mc])", file=sys.stderr)
        return 1
    port = int(config.section("media").get("port", protocol.DEFAULT_PORT))
    return run(port, {name: dict(entry or {}) for name, entry in displays.items()}, args.display)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    match args.command:
        case None:
            parser.print_help()
            return 0
        case "doctor":
            return _doctor()
        case "it":
            return _run(args)
        case "mc":
            return _mc(args)
        case command:
            print(f"vuk {command} isn't built yet.", file=sys.stderr)
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
