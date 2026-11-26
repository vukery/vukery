"""A test rig for the FAST platform: mock boards on fake serial ports, a fake host.

MPF's FAST tests boot a whole MPF machine. This rig boots only the platform,
the way vukery's engine will (initialize → configure switches and coils →
soft reset → start), and checks the same wire traffic. The expected commands
are read straight out of MPF's own test file, so MPF stays the source of truth.
"""

import ast
import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from tests.mpf_ported.fast import mock_fast
from vukery.devices.coil import Coil, CoilConfig
from vukery.devices.light import Light, LightConfig
from vukery.platforms.fast.config import FastConfig
from vukery.platforms.fast.fast import FastHardwarePlatform
from vukery.platforms.interfaces import (
    DriverSettings,
    PulseSettings,
    SerialPortInfo,
    SwitchConfig,
    SwitchSettings,
)

MPF_FAST = Path(__file__).parents[2] / "mpf_ported" / "fast"


def mpf_expected_commands(test_file: str, attribute: str = "net_cpu") -> dict[str, str]:
    """The ``expected_commands`` dict that an MPF FAST test sets up in ``create_expected_commands``."""
    tree = ast.parse((MPF_FAST / test_file).read_text())
    for node in ast.walk(tree):
        match node:
            case ast.FunctionDef(name="create_expected_commands", body=body):
                for statement in body:
                    match statement:
                        case ast.Assign(targets=[ast.Attribute(value=ast.Attribute(attr=attr),
                                                               attr="expected_commands")], value=value) \
                                if attr == attribute:
                            return ast.literal_eval(value)
                        case _:
                            pass
            case _:
                pass
    raise LookupError(f"No {attribute}.expected_commands in {test_file}")


def mpf_config(name: str) -> dict[str, Any]:
    return yaml.safe_load((MPF_FAST / "config" / name).read_text())


class SilentBoard(mock_fast.MockFastSerial):
    """A serial port with nothing answering (e.g. the unused ports of a Nano's FTDI chip)."""

    def write(self, msg):
        return len(msg)


class MockPort:
    """A ``SerialPort`` connected to one of MPF's mock FAST boards."""

    def __init__(self, board: mock_fast.MockFastSerial):
        self.board = board
        self.closed = False

    def write(self, data: bytes) -> None:
        self.board.write(data)

    async def read(self, n: int) -> bytes:
        while not self.closed:
            if self.board.queue:
                return self.board.read(n)
            await asyncio.sleep(0.001)
        return b""

    def close(self) -> None:
        self.closed = True


class _Repeating:
    def __init__(self, task: asyncio.Task[None]):
        self.task = task

    def cancel(self) -> None:
        self.task.cancel()


class FakeHost:
    """The ``PlatformHost`` for tests: records switch changes and stop requests."""

    def __init__(self, loop: asyncio.AbstractEventLoop, boards: dict[str, mock_fast.MockFastSerial],
                 serial_ports: list[SerialPortInfo] | None = None):
        self.loop = loop
        self.boards = boards
        self.serial_ports = serial_ports or []
        self.production = False
        self.is_shutting_down = False
        self.stopped: str | None = None
        self.calls: dict[str, asyncio.TimerHandle] = {}
        self.switches: dict[int, tuple[str, bool]] = {}  # hw number → (name, invert)
        self.switch_states: dict[str, int] = {}
        self.switch_events: list[tuple[str, int]] = []

    def list_serial_ports(self) -> list[SerialPortInfo]:
        return self.serial_ports

    async def open_serial(self, port: str, baud: int) -> MockPort:
        if port not in self.boards:
            raise OSError(f"No mock board on {port}")
        return MockPort(self.boards[port])

    def schedule_interval(self, callback: Callable[[], None], seconds: float) -> _Repeating:
        async def repeat() -> None:
            while True:
                await asyncio.sleep(seconds)
                callback()
        return _Repeating(self.loop.create_task(repeat()))

    def call_later(self, name: str, ms: int, callback: Callable[[], object]) -> None:
        self.cancel_call(name)
        self.calls[name] = self.loop.call_later(ms / 1000, callback)

    def cancel_call(self, name: str) -> None:
        if handle := self.calls.pop(name, None):
            handle.cancel()

    def add_switch(self, name: str, number: int, invert: bool) -> None:
        self.switches[number] = (name, invert)
        self.switch_states[name] = 0

    def switch_changed(self, platform: object, number: int, state: int) -> None:
        if number in self.switches:
            name, _ = self.switches[number]
            self.switch_states[name] = state
            self.switch_events.append((name, state))

    def sync_switch_states(self, platform: object, hw_states: dict[int, int]) -> None:
        for number, (name, invert) in self.switches.items():
            self.switch_states[name] = int(invert) ^ hw_states[number]

    def stop(self, reason: str) -> None:
        self.stopped = reason

    def create_task(self, coro: Any) -> asyncio.Task[Any]:
        return self.loop.create_task(coro)

    def now(self) -> float:
        return self.loop.time()


class FastRig:
    """Boots the FAST platform from an MPF test config against mock boards."""

    def __init__(self, config_file: str, boards: dict[str, mock_fast.MockFastSerial],
                 expected: dict[str, dict[str, str]], serial_ports: list[SerialPortInfo] | None = None,
                 auto_ports: bool = False):
        self.loop = asyncio.new_event_loop()
        self.config = mpf_config(config_file)
        self.boards = boards
        for port, commands in expected.items():
            boards[port].expected_commands = dict(commands)
        self.host = FakeHost(self.loop, boards, serial_ports)
        fast = {name: dict(section) if isinstance(section, dict) else section
                for name, section in self.config["fast"].items()}
        if auto_ports:
            for section in ("net", "rgb"):
                fast[section]["port"] = "auto"
        elif "rgb" in fast and fast["rgb"]["port"] not in boards:
            del fast["rgb"]  # no mock RGB board given: test NET only
        self.platform = FastHardwarePlatform(self.host, FastConfig.from_yaml(fast))
        self.coils: dict[str, Coil] = {}
        self.lights: dict[str, Light] = {}
        self.switches: dict[str, Any] = {}

    def run(self, coro: Any) -> Any:
        return self.loop.run_until_complete(coro)

    def settle(self, seconds: float = 0.05) -> None:
        self.run(asyncio.sleep(seconds))

    def start(self) -> None:
        """Boot the platform. If startup fails, everything is cleaned up before the error propagates."""
        try:
            self._start()
        except BaseException:
            self.stop()
            raise

    def _start(self) -> None:
        self.run(self.platform.initialize())
        for name, entry in (self.config.get("switches") or {}).items():
            invert = str(entry.get("type", "NO")).upper() == "NC"
            hw = self.platform.configure_switch(
                str(entry["number"]),
                SwitchConfig(name=name, invert=invert, debounce=entry.get("debounce", "auto")),
                entry.get("platform_settings"))
            self.switches[name] = (hw, invert)
            self.host.add_switch(name, hw.number, invert)
        for name, entry in (self.config.get("coils") or {}).items():
            self.coils[name] = Coil(CoilConfig.from_yaml(name, entry), self.platform,
                                    self.platform.features["max_pulse"])
        if "rgb" in self.platform.serial_connections:
            for name, entry in (self.config.get("lights") or {}).items():
                self.lights[name] = Light(LightConfig.from_yaml(name, entry), self.platform,
                                          self.lights, self.host.now)
        self.run(self.platform.soft_reset())
        self.platform.start()
        self.settle()

    def stop(self) -> None:
        if self.loop.is_closed():
            return
        self.platform.stop()
        self.settle()
        pending = [task for task in asyncio.all_tasks(self.loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.loop.close()

    # --- autofire coils (MPF: autofire_coils:), enough to set hardware rules

    def autofire(self, name: str) -> tuple[SwitchSettings, DriverSettings]:
        entry = self.config["autofire_coils"][name]
        coil = self.coils[entry["coil"]]
        hw_switch, invert = self.switches[entry["switch"]]
        reverse = bool(entry.get("reverse_switch", False))
        switch_settings = SwitchSettings(hw_switch=hw_switch, invert=invert ^ reverse, debounce=False)
        driver_settings = DriverSettings(
            hw_driver=coil.hw_driver,
            pulse_settings=PulseSettings(power=coil.pulse_power(), duration=coil.pulse_ms()),
            hold_settings=None,
            recycle=True,
        )
        return switch_settings, driver_settings

    def enable_autofire(self, name: str) -> None:
        self.platform.set_pulse_on_hit_rule(*self.autofire(name))

    def disable_autofire(self, name: str) -> None:
        self.platform.clear_hw_rule(*self.autofire(name))

    def unsent(self, port: str) -> dict[str, str]:
        """Expected commands that weren't sent (should be empty)."""
        return self.boards[port].expected_commands
