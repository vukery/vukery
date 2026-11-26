# Copied from the Mission Pinball Framework (MPF) 0.57.6:
# https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/platforms/fast/fast.py
# Copyright (c) The Mission Pinball Framework team and other contributors.
# MIT License: see vukery/_mpf/NOTICE.
"""FAST hardware platform: Nano and Neuron controllers.

Changes from MPF (trimmed to what vukery supports):
- Only the NET port (Nano and Neuron controllers) for now; RGB and EXP come
  next. Retro, audio, DMD, segment displays, servos, steppers, shakers, GI
  strings and matrix lights are gone.
- Built from a ``PlatformHost`` and a typed ``FastConfig`` instead of MPF's
  ``machine``. Lifecycle is explicit methods the host calls (``initialize``,
  ``soft_reset``, ``start``, ``stop``) instead of init-phase events.
- ``platform_settings`` for switches and coils get their FAST defaults here
  (MPF did that in its config validator).
- Port auto-detection isn't ported yet: ports must be set explicitly.
"""

import asyncio

from vukery.core.errors import ConfigError, HardwareError
from vukery.core.log import Logs
from vukery.core.util import Util
from vukery.platforms.fast.communicators.net_nano import FastNetNanoCommunicator
from vukery.platforms.fast.communicators.net_neuron import FastNetNeuronCommunicator
from vukery.platforms.fast.config import FastConfig
from vukery.platforms.fast.fast_driver import FASTDriver
from vukery.platforms.fast.fast_io_board import FastIoBoard
from vukery.platforms.fast.fast_switch import FASTSwitch
from vukery.platforms.interfaces import DriverConfig, DriverSettings, PlatformHost, SwitchConfig, SwitchSettings

SWITCH_PLATFORM_SETTINGS = {'debounce_open': None, 'debounce_close': None}
COIL_PLATFORM_SETTINGS = {'recycle_ms': None, 'pwm2_ms': None}


class FastHardwarePlatform(Logs):

    """Platform class for the FAST Pinball hardware."""

    features = {'tickless': True, 'max_pulse': 25500}

    def __init__(self, host: PlatformHost, config: FastConfig):
        """Initialize FAST hardware platform."""
        self.host = host
        self.config = config
        self.configure_logging("FAST", config.debug)

        if config.net is None:
            raise ConfigError("fast: needs a net: section")
        self.machine_type = config.net.controller

        self.serial_connections = dict()
        self.hw_switch_data = {i: 0 for i in range(112)}
        self.new_switch_data = asyncio.Event()  # Used to signal when we have updated switch data
        self.io_boards = dict()     # type: Dict[int, FastIoBoard]
        self.io_boards_by_name = dict()     # type: Dict[str, FastIoBoard]
        self.switches_initialized = False
        self.drivers_initialized = False

    def get_info_string(self):
        """Dump info strings about boards."""
        info_string = ""

        for port in sorted(self.serial_connections.keys()):
            info_string += f"{port.upper()}: {self.serial_connections[port].remote_model} " + \
                f"v{self.serial_connections[port].remote_firmware}\n"

        info_string += "\nI/O Boards:\n"
        for board in self.io_boards.values():
            info_string += board.get_description_string() + "\n"
        return info_string

    async def initialize(self):
        """Connect to every configured port and run each board's startup handshake."""
        await self._connect_to_hardware()

    async def soft_reset(self):
        """Soft reset the FAST controller.

        Used to reset / sync / verify all hardware configurations. This command does not perform a
        hard reset of the boards, rather it queries the boards for their current configuration and
        reapplies (with warnings) any configs that are out of sync.
        """
        self.debug_log("Soft resetting FAST platform.")
        for comm in self.serial_connections.values():
            await comm.soft_reset()

    def start(self):
        """Start the watchdog and periodic tasks. Called once switches and drivers are configured."""
        for comm in self.serial_connections.values():
            comm.start_watchdog()
            comm.start_tasks()

    def stop(self):
        """Stop the platform: expire the watchdog (coils off) and close the ports."""
        for conn in self.serial_connections.values():
            conn.stopping()
            conn.cancel_tasks()

        for connection in self.serial_connections.values():
            connection.stop()

        self.serial_connections = dict()

    def __repr__(self):
        """Return str representation."""
        return '[FAST Platform Interface]'

    def register_io_board(self, board: FastIoBoard):
        """Register a FAST I/O Board."""
        if board.node_id in self.io_boards:
            raise HardwareError("Duplicate node_id")
        self.io_boards[board.node_id] = board
        self.io_boards_by_name[board.name] = board

    async def _connect_to_hardware(self):
        net = self.config.net
        if 'auto' in net.port:
            raise ConfigError("fast: net: port: auto isn't supported by vukery yet. Set the port explicitly.")

        if net.controller == 'neuron':
            communicator = FastNetNeuronCommunicator(platform=self, processor='net', config=net)
        else:
            communicator = FastNetNanoCommunicator(platform=self, processor='net', config=net)

        await communicator.connect()
        await communicator.init()
        self.serial_connections['net'] = communicator

    async def get_hw_switch_states(self, query_hw=False):
        """Return a dict of hw switch states.

        If query_hw is True, will re-query the hardware for the current switch states. Otherwise it will just return
        the last cached value.
        """
        # If the switches have not been initialized then their states are garbage, so don't bother
        if self.switches_initialized and query_hw:
            self.new_switch_data.clear()
            await self.serial_connections['net'].update_switches_from_hardware()
            await self.new_switch_data.wait()  # Wait here until we have updated switch data

        return self.hw_switch_data

    def _parse_driver_number(self, number):
        try:
            board_str, driver_str = number.split("-")
        except ValueError:  # If there's no dash, assume it's a driver number
            return int(number, 16)

        try:
            board = self.io_boards_by_name[board_str]
        except KeyError:
            raise ConfigError(f"I/O Board {board_str} does not exist for driver {number}")

        driver = int(driver_str)

        if board.driver_count <= driver:
            raise ConfigError(f"I/O Board {board} only has drivers 0-{board.driver_count - 1}. "
                              f"Driver value {driver} is not valid.")

        index = board.start_driver + driver

        if index + 1 > self.serial_connections['net'].MAX_DRIVERS:
            raise ConfigError(
                f"I/O Board {board} driver {driver} is out of range. This would be driver {index + 1} "
                f"but this platform supports a max of {self.serial_connections['net'].MAX_DRIVERS} drivers.")

        return index

    def configure_driver(self, config: DriverConfig, number: str, platform_settings: dict | None = None) -> FASTDriver:
        """Configure a driver."""
        if not self.serial_connections.get('net'):
            raise HardwareError('A request was made to configure a FAST driver, but no connection to a NET '
                                'processor is available')

        if not number:
            raise ConfigError("Driver needs a number")

        index = self._parse_driver_number(str(number))
        driver = self.serial_connections['net'].drivers[index]  # contains all drivers on the board
        driver.set_initial_config(config, {**COIL_PLATFORM_SETTINGS, **(platform_settings or {})})
        return driver

    def _parse_switch_number(self, number):
        try:
            board_str, switch_str = number.split("-")
        except ValueError as e:
            total_switches = 0
            for board_obj in self.io_boards.values():
                total_switches += board_obj.switch_count
            index = Util.int_to_hex_string(number)

            if int(index, 16) >= total_switches:
                raise ConfigError(f"Switch {int(index, 16)} does not exist. Only "
                                  f"{total_switches} switches found. Switch number: {number}") from e

            return index

        try:
            board = self.io_boards_by_name[board_str]
        except KeyError:
            raise ConfigError(f"Board {board_str} does not exist for switch {number}")

        switch = int(switch_str)

        if board.switch_count <= switch:
            raise ConfigError(f"Board {board} only has switches 0-{board.switch_count - 1}. "
                              f"Switch value {switch} is not valid.")

        return Util.int_to_hex_string(board.start_switch + switch)

    def configure_switch(self, number: str, config: SwitchConfig, platform_settings: dict | None = None) -> FASTSwitch:
        """Configure the switch object for a FAST Pinball controller."""
        if not number:
            raise ConfigError("Switch needs a number")

        if not self.serial_connections.get('net'):
            raise HardwareError("A request was made to configure a FAST switch, but no connection to a NET "
                                "processor is available")

        try:
            number = self._parse_switch_number(str(number))
        except ValueError:
            raise ConfigError(f"Could not parse switch number {config.name}/{number}. Seems "
                              "to be not a valid switch number for the FAST platform.")

        switch = self.serial_connections['net'].switches[int(number, 16)]
        switch.set_initial_config(config, {**SWITCH_PLATFORM_SETTINGS, **(platform_settings or {})})
        return switch

    def set_pulse_on_hit_rule(self, enable_switch: SwitchSettings, coil: DriverSettings):
        """Set pulse on hit rule on driver.

        Pulses a driver when a switch is hit. When the switch is released the pulse continues. Typically used for
        autofire coils such as pop bumpers.

        FAST Driver Mode 10 or 70, depending on settings
        """
        coil.hw_driver.set_hardware_rule(None, enable_switch, coil)

    def set_delayed_pulse_on_hit_rule(self, enable_switch: SwitchSettings, coil: DriverSettings, delay_ms: int):
        """Pulse a driver when a switch is hit, after a delay. Typically used for kickbacks.

        FAST Driver Mode 30
        """
        coil.hw_driver.set_hardware_rule('30', enable_switch, coil, delay_ms=delay_ms)

    def set_pulse_on_hit_and_release_rule(self, enable_switch, coil):
        """Pulse on hit, cancel on release. The main coil of a dual-wound flipper without EOS.

        FAST Driver Mode 18 (with pwm2_power = 00)
        """
        coil.hold_settings = None
        coil.hw_driver.set_hardware_rule('18', enable_switch, coil)

    def set_pulse_on_hit_and_enable_and_release_rule(self, enable_switch: SwitchSettings, coil: DriverSettings):
        """Pulse on hit, then hold, until release. Single-wound flippers.

        FAST Driver Mode 18 (with pwm2_power != 00)
        """
        coil.hw_driver.set_hardware_rule('18', enable_switch, coil)

    def set_pulse_on_hit_and_release_and_disable_rule(self, enable_switch: SwitchSettings,
                                                      eos_switch: SwitchSettings, coil: DriverSettings,
                                                      repulse_settings=None):
        """Pulse on hit; stop on release or when EOS closes. The main coil of a dual-wound flipper with EOS.

        FAST Driver Mode 75
        """
        del repulse_settings  # TODO do we want to implement software repulse?
        off_switch = eos_switch.hw_switch.hw_number
        coil.hw_driver.set_hardware_rule('75', enable_switch, coil, off_switch=off_switch)

    def set_pulse_on_hit_and_enable_and_release_and_disable_rule(self, enable_switch: SwitchSettings,
                                                                 eos_switch: SwitchSettings, coil: DriverSettings,
                                                                 repulse_settings=None):
        """Pulse on hit then hold; release disables; EOS switches to hold. Single-wound flippers with EOS.

        FAST Driver Mode 20
        """
        coil.hw_driver.set_hardware_rule('20', enable_switch, coil, eos_switch=eos_switch,
                                         repulse_settings=repulse_settings)

    def clear_hw_rule(self, switch, coil):
        """Clear a hardware rule."""
        self.debug_log("Clearing HW Rule for switch: %s, coils: %s",
                       switch.hw_switch.number, coil.hw_driver.number)

        # TODO: check that the rule is switch + coil and not another switch + this coil

        driver = coil.hw_driver

        driver.clear_autofire()
