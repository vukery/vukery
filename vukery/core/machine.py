"""The machine: config, hardware platform, devices and modes, wired together.

It's also the ``PlatformHost`` that hardware platforms talk to.

Startup, in order:

1. load the config (shared files, then the environment's);
2. create the platform for ``hardware: platform:`` (``development`` and
   ``test`` by default; ``fast`` needs ``--hardware`` outside production);
3. connect to the hardware, then create switches, coils, lights, ball
   devices, flippers and autofire coils;
4. load the built-in modes (attract, game) and the game's own;
5. post ``init_done`` and ``reset_complete``. Attract starts on the second.
"""

import asyncio
import hashlib
import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

from vukery.core.clock import Clock, RealClock
from vukery.core.config import GameConfig, load_game_config
from vukery.core.errors import ConfigError
from vukery.core.events import EventManager
from vukery.core.log import Logs
from vukery.core.modes import Mode, ModeController
from vukery.core.shows import Shows
from vukery.core.switches import SwitchConfig, SwitchController
from vukery.devices.ball_device import BallDevice, BallDeviceConfig
from vukery.devices.coil import Coil, CoilConfig
from vukery.devices.light import Light, LightConfig
from vukery.devices.light_group import LightGroup
from vukery.devices.rules import AutofireCoil, Flipper
from vukery.media import dashboard, keyboard, protocol
from vukery.media.scenes import build, scene_name
from vukery.media.server import DisplayConfig, MediaServer
from vukery.media.sounds import Sounds
from vukery.modes.attract import Attract
from vukery.modes.built_in import BuiltInMode, resolve
from vukery.modes.game import Game
from vukery.modes.high_score import HighScore
from vukery.modes.tilt import Tilt
from vukery.platforms.interfaces import SerialPortInfo
from vukery.platforms.simulated import SimulatedPlatform

BUILT_IN_MODES: tuple[type[BuiltInMode], ...] = (Attract, Game)   # always loaded
OPTIONAL_MODES: dict[str, type[BuiltInMode]] = {mode.name: mode for mode in (HighScore, Tilt)}   # when listed in modes:


class Machine(Logs):
    """A pinball machine, real or simulated."""

    def __init__(self, config: GameConfig, clock: Clock | None = None, hardware: bool = False,
                 dashboard: bool = False):
        self.config = config
        self.environment = config.environment
        self.production = config.environment == "production"
        self.is_shutting_down = False
        self.stopped_reason: str | None = None
        self.configure_logging("machine")

        loop = clock.loop if clock else asyncio.new_event_loop()
        self.clock: Clock = clock or RealClock(loop)
        self.loop = self.clock.loop
        self.events = EventManager(self.loop)
        self.switches = SwitchController(self.events, self.clock)
        self.modes = ModeController(self)
        self.shows = Shows(self)
        self.game: Game | None = None
        self.coils: dict[str, Coil] = {}
        self.lights: dict[str, Light] = {}
        self.light_groups: dict[str, LightGroup] = {}
        self.ball_devices: dict[str, BallDevice] = {}
        self.flippers: dict[str, Flipper] = {}
        self.autofire_coils: dict[str, AutofireCoil] = {}
        self.keyboard: dict[str, keyboard.Key] = {}
        self.data_dir = config.game_dir / "data"   # what the machine keeps (high scores…); specs use a temp folder
        self._calls: dict[str, Any] = {}
        try:
            self.platform = self._create_platform(hardware)
            displays = {name: DisplayConfig.from_yaml(name, entry or {})
                        for name, entry in config.section("displays").items()}
            port = int(config.section("media").get("port", protocol.DEFAULT_PORT))
            self.sounds = Sounds.load(config.game_dir, config.section("sound_system"), config.section("sounds"),
                                      config.section("sound_pools"))
            # A media server runs when there's something to show or play: displays, sounds, or vuk me.
            self.media: MediaServer | None = (MediaServer(self, displays, port)
                                              if displays or dashboard or self.sounds.sounds else None)
        except BaseException:
            if clock is None:  # the loop is ours: don't leave it (and its sockets) open
                self.loop.close()
            raise

    @classmethod
    def from_folder(cls, game_dir: Path, env: str | None = None, clock: Clock | None = None,
                    hardware: bool = False, dashboard: bool = False) -> Machine:
        return cls(load_game_config(game_dir, env), clock=clock, hardware=hardware, dashboard=dashboard)

    # --- platform

    def _create_platform(self, hardware: bool) -> Any:
        name = self.config.platform
        match name, self.environment:
            case "development" | "test", _:
                return SimulatedPlatform(self, simulate_balls=name == "development")
            case "fast", "test":
                raise ConfigError("The test environment never uses real hardware (hardware: platform: fast)")
            case "fast", "development" if not hardware:
                raise ConfigError("Real hardware in development needs --hardware")
            case "fast", _:
                from vukery.platforms.fast.config import FastConfig
                from vukery.platforms.fast.fast import FastHardwarePlatform
                return FastHardwarePlatform(self, FastConfig.from_yaml(self.config.section("fast")))
            case other, _:
                raise ConfigError(f"hardware: platform: {other!r} isn't supported (development, test or fast)")

    def media_controllers(self) -> list[str]:
        """The displays that need a media controller: one per display in ``displays:``, or none.

        The config alone decides; there's no command-line switch.
        """
        return list(self.media.displays) if self.media is not None else []

    def plays_sound(self) -> bool:
        """Whether there's anything to play: a file in assets/sounds/, or a sounds: entry."""
        return bool(self.sounds.sounds)

    def platform_is_simulated(self) -> bool:
        """The development or test platform: switches can be set from code and from vuk me."""
        return isinstance(self.platform, SimulatedPlatform)

    def platform_simulates_balls(self) -> bool:
        return isinstance(self.platform, SimulatedPlatform) and self.platform.simulate_balls

    # --- startup and shutdown

    async def start(self) -> None:
        await self.platform.initialize()
        self._create_devices()
        dashboard.config(self)  # checks dashboard: playfield: names, whether or not vuk me runs
        await self.platform.soft_reset()
        self.platform.start()
        if self.config.platform == "development":
            self._fill_troughs()
        self._load_modes()
        self.shows.load(self.config.game_dir, list(self.config.modes))
        if self.media is not None:
            for mode in self.modes.modes.values():
                for function in mode.scene_functions():
                    self.media.define(scene_name(function), build(function), mode.name)
            if self.environment != "test":
                await self.media.serve()
        self.events.post("init_done")
        self.events.post("reset_complete")

    def _create_devices(self) -> None:
        config = self.config
        for name, entry in config.section("switches").items():
            self.switches.add(SwitchConfig.from_yaml(name, entry or {}), self.platform)
        for name, entry in config.section("coils").items():
            self.coils[name] = Coil(CoilConfig.from_yaml(name, entry or {}), self.platform,
                                    self.platform.features["max_pulse"])
        for name, entry in config.section("lights").items():
            self.lights[name] = Light(LightConfig.from_yaml(name, entry or {}), self.platform, self.lights, self.now)
        for name, members in config.section("light_groups").items():
            self.light_groups[name] = LightGroup.from_yaml(name, members, self.lights)
        for name, entry in config.section("ball_devices").items():
            device = BallDeviceConfig.from_yaml(name, entry or {})
            if "trough" not in device.tags and not device.mechanical_eject:
                raise ConfigError(f"ball_devices: {name}: only troughs (tags: trough) and plunger lanes "
                                  "(mechanical_eject: true) are supported so far")
            self.ball_devices[name] = BallDevice(device, self)
        for device in self.ball_devices.values():
            for target in device.config.eject_targets:
                if target != "playfield" and target not in self.ball_devices:
                    raise ConfigError(f"ball_devices: {device.name}: eject_targets: no ball device named "
                                      f"{target!r} (or use playfield)")
        for name, entry in config.section("flippers").items():
            self.flippers[name] = Flipper.from_yaml(name, entry or {}, self)
        for name, entry in config.section("autofire_coils").items():
            self.autofire_coils[name] = AutofireCoil.from_yaml(name, entry or {}, self)
        self.keyboard = keyboard.load(config.section("keyboard"), set(self.switches.switches))  # vuk me's keys
        self.events.add_handler("request_to_start_game", self._balls_home_check, priority=100)

    def _fill_troughs(self) -> None:
        """development: every ball starts in the trough, like MPF's smart_virtual platform."""
        for device in self.ball_devices.values():
            if "trough" not in device.config.tags:
                continue
            for name in device.config.ball_switches:
                if not self.switches[name].state:
                    self.set_switch(name, 1)

    def _load_modes(self) -> None:
        """vukery's built-in modes, each customized or (if optional) replaced by the game's mode of the
        same name, then the game's own."""
        check_mode_folders(self.config.game_dir)
        package = modes_package(self.config.game_dir)
        mine: dict[str, type[Mode]] = {}
        for name in self.config.modes:
            if name in OPTIONAL_MODES and not (self.config.game_dir / "modes" / name).is_dir():
                mine[name] = OPTIONAL_MODES[name]   # vukery's, as it is
            else:
                mine[name] = load_mode(self.config.game_dir, name, package)
        for name in [n for n in mine if n in OPTIONAL_MODES]:
            mine[name] = resolve(OPTIONAL_MODES[name], mine[name])
        for built_in in BUILT_IN_MODES:
            mode_class = resolve(built_in, mine.pop(built_in.name)) if built_in.name in mine else built_in
            self.modes.add(mode_class(self))
        for mode_class in mine.values():
            self.modes.add(mode_class(self))

    def stop(self, reason: str = "") -> None:
        if self.is_shutting_down:
            return
        self.is_shutting_down = True
        self.stopped_reason = reason
        self.warning_log("Stopping: %s", reason or "requested")
        if self.media is not None:
            self.media.stop()
        self.platform.stop()
        self.events.stop()

    def adjust_score(self, points: float, source: str | None) -> int:
        """Pass points through every running mode's ``adjust_score``, highest priority first."""
        for mode in self.modes.running():
            if type(mode).adjust_score is not Mode.adjust_score:
                points = mode.adjust_score(points, source)
        return round(points)

    def trough(self) -> BallDevice | None:
        for device in self.ball_devices.values():
            if "trough" in device.config.tags:
                return device
        return None

    def _balls_home_check(self, **_: Any) -> bool:
        home = [d for d in self.ball_devices.values() if "home" in d.config.tags or "trough" in d.config.tags]
        if all(d.is_full for d in home):
            return True
        self.warning_log("Not starting a game: not every ball is home (%s)",
                         ", ".join(f"{d.name} {d.balls}/{d.capacity}" for d in home))
        return False

    # --- switches from code (simulation, tests, vuk me)

    def set_switch(self, name: str, state: int) -> None:
        """Change a switch as the hardware would. Only on the simulated platforms."""
        if not isinstance(self.platform, SimulatedPlatform):
            raise ConfigError("Switches can only be set by code on the development and test platforms")
        self.platform.set_switch(self.switches[name].config.number, state)

    # --- PlatformHost

    def now(self) -> float:
        return self.clock.now()

    def create_task(self, coro: Any) -> asyncio.Task[Any]:
        return self.loop.create_task(coro)

    def switch_changed(self, platform: object, number: int, state: int) -> None:
        self.switches.hw_changed(platform, number, state)

    def sync_switch_states(self, platform: object, hw_states: dict[int, int]) -> None:
        self.switches.hw_sync(platform, hw_states)

    def call_later(self, name: str, ms: int, callback: Callable[[], object]) -> None:
        self.cancel_call(name)
        self._calls[name] = self.clock.call_later(ms / 1000, callback)

    def cancel_call(self, name: str) -> None:
        if timer := self._calls.pop(name, None):
            timer.cancel()

    def schedule_interval(self, callback: Callable[[], None], seconds: float) -> Any:
        async def repeat() -> None:
            while True:
                await self.clock.sleep(seconds)
                callback()
        return self.create_task(repeat())

    async def open_serial(self, port: str, baud: int) -> Any:
        from vukery.platforms.serial_port import open_serial
        return await open_serial(port, baud)

    def list_serial_ports(self) -> list[SerialPortInfo]:
        from vukery.platforms.serial_port import list_serial_ports
        return list_serial_ports()


NOT_MODES = {"vukery", "__pycache__"}  # modes/vukery/ is for overrides, not a mode


def check_mode_folders(game_dir: Path) -> None:
    """Every folder in ``modes/`` is a mode, so each needs a ``mode.py``.

    ``modes/vukery/`` (overrides) and hidden or cache folders are skipped;
    folders inside a mode aren't modes.
    """
    modes = game_dir / "modes"
    if not modes.is_dir():
        return
    missing = sorted(folder.name for folder in modes.iterdir()
                     if folder.is_dir() and folder.name not in NOT_MODES and not folder.name.startswith(".")
                     and not (folder / "mode.py").is_file())
    for name in missing:  # named the old way: say exactly what to rename
        if (modes / name / f"{name}.py").is_file():
            raise ConfigError(f"modes: {name}: a mode's main file is mode.py: rename "
                              f"{modes / name / f'{name}.py'} to {modes / name / 'mode.py'}")
    if missing:
        raise ConfigError("every folder in modes/ is a mode, with its class in mode.py. No mode.py in: "
                          + ", ".join(f"modes/{name}/" for name in missing))


def modes_package(game_dir: Path) -> str:
    """Make the machine's ``modes/`` folder a Python package, and return its name.

    That lets a mode split itself into files and import them
    (``from .scoring import SCORING`` in ``modes/base/mode.py``). Splitting is
    optional: a mode can live in one file. Every machine gets its own package
    name, and its modules are loaded fresh each time the machine starts.
    """
    package = "vukery_modes_" + hashlib.sha1(str(game_dir.resolve()).encode()).hexdigest()[:12]
    for loaded in [m for m in sys.modules if m == package or m.startswith(package + ".")]:
        del sys.modules[loaded]
    module = ModuleType(package)
    module.__path__ = [str(game_dir / "modes")]
    module.__package__ = package
    sys.modules[package] = module
    importlib.invalidate_caches()
    return package


def load_mode(game_dir: Path, name: str, package: str | None = None) -> type[Mode]:
    """Find the ``Mode`` subclass for ``name`` in ``modes/<name>/mode.py``."""
    package = package or modes_package(game_dir)
    path = game_dir / "modes" / name / "mode.py"
    if not path.is_file():
        for old in (game_dir / "modes" / name / f"{name}.py", game_dir / "modes" / f"{name}.py"):
            if old.is_file():
                raise ConfigError(f"modes: {name}: a mode's main file is mode.py: rename {old} to {path}")
        raise ConfigError(f"modes: {name}: no {path}")
    module_name = f"{package}.{name}.mode"
    module = importlib.import_module(module_name)
    found = [obj for obj in vars(module).values()
             if isinstance(obj, type) and issubclass(obj, Mode) and obj.__module__ == module.__name__]
    match [cls for cls in found if cls.name == name], found:
        case [mode_class], _:
            return mode_class
        case [], [mode_class]:
            raise ConfigError(f"modes: {name}: {path} defines {mode_class.__name__}, whose mode name is "
                              f"{mode_class.name!r}. Rename the class or set name = {name!r}.")
        case _:
            raise ConfigError(f"modes: {name}: expected one Mode subclass named for the mode in {path}")
