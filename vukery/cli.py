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
               "default development; vuk you always uses test). VUK_LOG sets one log level for "
               "everything (debug, info, warning or error); per-component levels go in the logging: config.",
    )
    parser.add_argument("--version", action="version", version=f"vukery {__version__}")
    parser.add_argument("-C", dest="game_dir", metavar="DIR", default=".",
                        help="the game folder (default: the current folder)")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    it = commands.add_parser("it", help="create a new machine folder, ready to play and test (MPF: mpf create_config)")
    it.add_argument("name", nargs="?", help="the folder to create; its name is the machine's name, e.g. combat "
                                           "(asked for if left out)")

    us = commands.add_parser("us", help="run the game, displays full screen, no dashboard: how a machine runs "
                                            "(MPF: mpf both)")
    me = commands.add_parser("me", help="run the game with the vuk me dashboard, to play it on "
                                        "your computer (MPF: mpf both plus mpf monitor)")
    for run in (us, me):
        run.add_argument("--hardware", action="store_true", help="use real hardware in development")
        run.add_argument("--preload", action="store_true", help="load every asset at startup (MPF: -f)")
        run.add_argument("--log-dir", default="log", help="where log files go (default: log/)")

    commands.add_parser("top", help="terminal dashboard of a running game (MPF: mpf -t)")
    commands.add_parser("console", help="Python prompt attached to the running game (MPF: mpf service)")

    hardware = commands.add_parser("hardware", help="talk to the hardware directly (MPF: mpf hardware)")
    hardware.add_argument("action", choices=("scan", "switches", "lights", "coil"),
                          help="scan: boards and firmware; switches: live switch states; "
                               "lights: walk every LED; coil: pulse one coil (asks first)")
    hardware.add_argument("name", nargs="?", help="the coil to pulse (for: coil)")

    commands.add_parser("doctor", help="check the setup: versions, FFmpeg, serial ports (MPF: mpf diagnosis)")
    commands.add_parser("wire", help="FAST wiring instructions for the config (MPF: mpf wire)")

    you = commands.add_parser("you", aliases=["test"],
                              help="run the machine's specs, in the test environment (MPF: mpf test)")
    you.add_argument("pytest_args", nargs=argparse.REMAINDER, help="passed to pytest, e.g. -k scoring")

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


def _create(args: argparse.Namespace) -> int:
    """vuk it NAME: create a machine folder."""
    from pathlib import Path

    from vukery.core.errors import VukeryError
    from vukery.generator import create_machine

    name = args.name
    while not name:
        try:
            name = input("Name your machine (e.g. combat): ").strip()
        except EOFError:
            print("\nvuk it: no name given", file=sys.stderr)
            return 1
    folder = Path(args.game_dir) / name
    try:
        created = create_machine(folder)
    except VukeryError as e:
        print(f"vuk it: {e}", file=sys.stderr)
        return 1
    for path in created:
        print(f"      create  {path}")
    print(f"\nGet VUKed! Your machine is in {folder}. Next:\n\n"
          f"  cd {folder}\n  uv sync          # install vukery and the test tools\n"
          f"  uv run vuk me    # play it, with the dashboard\n  uv run vuk you   # run its specs")
    return 0


def _specs(args: argparse.Namespace) -> int:
    """vuk you: run the machine folder's specs with pytest, in the test environment."""
    import importlib.util
    import os
    from pathlib import Path

    folder = Path(args.game_dir).resolve()
    if not (folder / "config").is_dir():
        print(f"vuk you: {folder} isn't a machine folder (it has no config/ folder)", file=sys.stderr)
        return 1
    if importlib.util.find_spec("pytest") is None:
        print("vuk you: the specs need pytest (uv add --dev pytest pytest-describe pytest-spec)", file=sys.stderr)
        return 1
    environment = {**os.environ, "VUK_ENV": "test"}  # specs always run in test: no hardware, ever
    return subprocess.run([sys.executable, "-m", "pytest", *args.pytest_args], cwd=folder,
                          env=environment, check=False).returncode


def _run(args: argparse.Namespace) -> int:
    """Run the game in the game folder until Ctrl-C (or "quit").

    ``vuk us`` starts a full-screen media controller per display. ``vuk me``
    starts the dashboard instead, which shows the displays in its own panes, and stops
    the game when the dashboard closes.
    """
    import asyncio
    import importlib.util
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
        dashboard = args.command == "me"
        if dashboard and importlib.util.find_spec("pyglet") is None:
            print("vuk me: the dashboard needs pyglet (install vukery[mc])", file=sys.stderr)
            return 1
        machine = Machine(config, hardware=args.hardware, dashboard=dashboard)
    except VukeryError as e:
        print(f"vuk {args.command}: {e}", file=sys.stderr)
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

    async def until_closed(process: Any) -> None:
        """vuk me: the game runs while the dashboard is open."""
        while process.poll() is None:
            await asyncio.sleep(0.2)
        machine.stop("the dashboard closed")

    media_controllers: list[Any] = []
    try:
        loop.run_until_complete(machine.start())
        print(f"vukery is running {game_dir.name} ({config.environment}). Ctrl-C to stop.")
        if dashboard:
            assert machine.media is not None
            media_controllers = [subprocess.Popen([sys.executable, "-m", "vukery.dashboard", str(machine.media.port)])]
            loop.run_until_complete(until_closed(media_controllers[0]))
        elif config.platform == "development":
            media_controllers = _start_media_controllers(game_dir, machine.media_controllers())
            if sys.stdin.isatty():
                print("Type a switch name and press Enter to tap it, e.g. s_start.")
            loop.run_until_complete(type_switches())
        else:
            media_controllers = _start_media_controllers(game_dir, machine.media_controllers())
            loop.run_forever()
    except KeyboardInterrupt:
        machine.stop("Ctrl-C")
    except VukeryError as e:
        print(f"vuk {args.command}: {e}", file=sys.stderr)
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
    """One full-screen media controller process per display (they exit when the engine says bye)."""
    return [subprocess.Popen([sys.executable, "-m", "vukery.mc", str(game_dir), "--display", name])
            for name in displays]


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args, unknown = parser.parse_known_args(argv)
    match args.command, unknown:
        case "you" | "test", _:
            args.pytest_args = [*unknown, *args.pytest_args]  # options like -k go to pytest
        case _, [_, *_]:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")
        case _:
            pass
    match args.command:
        case None:
            parser.print_help()
            return 0
        case "doctor":
            return _doctor()
        case "it":
            return _create(args)
        case "you" | "test":  # vuk test is an alias
            return _specs(args)
        case "us" | "me":
            return _run(args)
        case command:
            print(f"vuk {command} isn't built yet.", file=sys.stderr)
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
