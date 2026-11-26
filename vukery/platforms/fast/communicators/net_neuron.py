# Copied from the Mission Pinball Framework (MPF) 0.57.6:
# https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/platforms/fast/communicators/net_neuron.py
# Copyright (c) The Mission Pinball Framework team and other contributors.
# MIT License: see vukery/_mpf/NOTICE.
"""FAST Neuron Serial Communicator.

Changes from MPF:
- Typed config (``config.io_loop`` holds ``IoBoardConfig`` objects).
- Switch changes go to ``host.switch_changed`` / ``host.sync_switch_states``
  instead of MPF's switch controller.
- I/O boards are always queried (MPF skipped it when no switches or coils
  were configured).
- Config and firmware errors raise vukery errors instead of ``AssertionError``.
"""

from packaging import version

from vukery.core.errors import ConfigError, HardwareError
from vukery.core.util import Util
from vukery.platforms.fast.communicators.base import FastSerialCommunicator
from vukery.platforms.fast.fast_io_board import FastIoBoard
from vukery.platforms.fast.fast_driver import FastDriverConfig
from vukery.platforms.fast.fast_switch import FASTSwitch
from vukery.platforms.fast.fast_driver import FASTDriver
from vukery.platforms.fast import fast_defines


class FastNetNeuronCommunicator(FastSerialCommunicator):

    """Serial communicator for the Neuron board."""

    MIN_FW = version.parse('2.06')
    IO_MIN_FW = version.parse('1.09')
    MAX_IO_BOARDS = 9
    MAX_SWITCHES = 104
    MAX_DRIVERS = 48
    IGNORED_MESSAGES = ['WD:P', 'TL:P']
    TRIGGER_CMD = 'TL'
    DRIVER_CMD = 'DL'
    SWITCH_CMD = 'SL'

    def __init__(self, platform, processor, config):
        """Initialize the Neuron controller."""
        super().__init__(platform, processor, config)

        self.io_loop = config.board_names_in_order()  # names, by position in the loop
        if len(self.io_loop) > self.MAX_IO_BOARDS:
            raise ConfigError(f"The {type(self).__name__} supports {self.MAX_IO_BOARDS} I/O boards, "
                              f"but {len(self.io_loop)} are configured.")
        self.switches = list()
        self.drivers = list()

        self.message_processors['SA:'] = self._process_sa
        self.message_processors['CH:'] = self._process_ch
        self.message_processors['!B:'] = self._process_boot_message
        self.message_processors['\x11\x11!'] = self._process_reboot_done
        self.message_processors['NN:'] = self._process_nn
        self.message_processors[f'{self.DRIVER_CMD}:'] = self.process_driver_config_msg
        self.message_processors[f'{self.SWITCH_CMD}:'] = self.process_switch_config_msg
        self.message_processors[f'/{self.SWITCH_CMD[-1]}:'] = self._process_switch_open
        self.message_processors[f'-{self.SWITCH_CMD[-1]}:'] = self._process_switch_closed

    async def init(self):
        """Initialize the hardware switches and drivers."""
        self.create_switches()
        self.create_drivers()

        # Loop here until we get a response
        await self.send_and_wait_for_response_processed('ID:', 'ID:', max_retries=-1)
        await self.configure_hardware()

        # Force expire the watchdog since who knows what state the board is in?
        self.send_and_forget('WD:1')
        await self.query_io_boards()

    async def configure_hardware(self):
        """Send the hardware configuration command."""
        await self.send_and_wait_for_response_processed(
            f'CH:{fast_defines.HARDWARE_KEY[self.platform.machine_type]},FF', 'CH:')

    def create_switches(self):
        """Track switches for the FAST loop.

        Neuron tracks all switches regardless of how many are connected.
        """
        for i in range(self.MAX_SWITCHES):
            self.switches.append(FASTSwitch(self, i))

    def create_drivers(self):
        """Track drivers for the FAST loop.

        Neuron tracks all drivers regardless of how many are connected.
        """
        for i in range(self.MAX_DRIVERS):
            self.drivers.append(FASTDriver(self, i))

    async def soft_reset(self, **kwargs):
        """Reset the NET processor."""
        del kwargs
        await self.reset_switches()
        await self.reset_drivers()
        await self.platform.get_hw_switch_states(query_hw=True)

    async def clear_board_serial_buffer(self):
        """Clear out the serial buffer."""

    def _process_boot_message(self, msg):
        """Reset the NET CPU."""
        del msg
        self.log.info("Resetting NET Processor...")

    def _process_reboot_done(self, msg):
        del msg
        self.log.info("Processor reset complete.")

    async def reset_switches(self):
        """Query the NET processor to get a list of switches and their configurations.

        Compare that to how they should be configured, and send new configuration
        commands for any that are different.
        """
        for switch in self.switches:
            await self.send_and_wait_for_response_processed(
                f'{self.SWITCH_CMD}:{switch.hw_number}', f'{self.SWITCH_CMD}:{switch.hw_number}')

        self.platform.switches_initialized = True

    async def reset_drivers(self):
        """Query the NET processor to get a list of drivers and their configurations.

        Compare that to how they should be configured, and send new configuration
        commands for any that are different.
        """
        for driver in self.drivers:
            await self.send_and_wait_for_response_processed(
                f'{self.DRIVER_CMD}:{Util.int_to_hex_string(driver.number)}', f"{self.DRIVER_CMD}:")

        self.platform.drivers_initialized = True

    def _process_ch(self, msg):
        if msg == 'F':
            raise HardwareError("Could not configure hardware. Check your FAST config.")

        self.done_processing_msg_response()

    async def query_io_boards(self):
        """Walk through the I/O boards in the config to verify the physical boards match the config."""
        current_node = 0
        while current_node < len(self.config.io_loop):
            await self.send_and_wait_for_response_processed('NN:{:02X}'.format(current_node), 'NN:')
            # Only move on once this node registered (a failed response is retried)
            if current_node + 1 >= len(self.platform.io_boards):
                current_node += 1

    def _process_nn(self, msg):
        firmware_ok = True

        if msg == 'F':  # NN:F
            return  # TODO now what?

        node_id, model, fw, dr, sw, _, _, _, _, _, _ = msg.split(',')

        node_id = Util.hex_string_to_int(node_id)
        dr = Util.hex_string_to_int(dr)
        sw = Util.hex_string_to_int(sw)
        model = model.strip('\x00')
        model = model.strip()

        # Remove the revision dash if it's there
        model = ('-').join(model.split('-')[:3])

        name = self.io_loop[node_id]

        if not model or model == '!Node Not Found!':
            self.log.error("No node board found at I/O position %s, board %s will not be available. " +
                           "Please check your cable connections.", node_id, name)
            self.done_processing_msg_response()  # TODO good candidate for retry option
            return

        if node_id in self.platform.io_boards:
            self.done_processing_msg_response()
            return

        model_string_from_config = ('-').join(self.config.io_loop[name].model.split('-')[:3]).upper()

        if model != model_string_from_config:
            raise ConfigError(f"I/O board config error. Board {node_id} is reporting as model {model}, "
                              f"but the config file says it's model {model_string_from_config}")

        prior_sw = 0
        prior_drv = 0

        for i in range(node_id):
            prior_sw += self.platform.io_boards[i].switch_count
            prior_drv += self.platform.io_boards[i].driver_count

        self.platform.register_io_board(FastIoBoard(self, name, node_id, model, fw, sw, dr, prior_sw, prior_drv))

        self.log.info('Registered I/O Board %s: Model: %s, Firmware: %s, Switches: %s, Drivers: %s',
                      node_id, model, fw, sw, dr)

        min_fw = self.IO_MIN_FW  # TODO move to IO board class
        if min_fw > version.parse(fw):
            self.log.critical("Firmware version mismatch. vukery requires the I/O boards "
                              "to be firmware %s, but your Board %s (%s) is firmware %s",
                              min_fw, node_id, model, fw)
            firmware_ok = False

        if not firmware_ok:
            raise HardwareError("Exiting due to I/O board firmware mismatch")

        self.done_processing_msg_response()

    def process_driver_config_msg(self, msg):
        """Handle an incoming DL/DN: message."""
        if msg == 'P':
            self.done_processing_msg_response()
            return

        # From here we know it's a config response
        current_hw_driver_config = FastDriverConfig(*msg.split(','))
        try:
            driver_obj = self.drivers[int(current_hw_driver_config.number, 16)]
        except IndexError:
            return  # we might get a config for a driver that doesn't exist, no worries

        if driver_obj.current_driver_config != current_hw_driver_config:
            driver_obj.send_config_to_driver()
        else:
            self.done_processing_msg_response()

    def process_switch_config_msg(self, msg):
        """Incoming SL:<switch_id>,<mode>,<debounce_close>,<debounce_open> message."""
        if msg == 'P':  # SL:P
            self.done_processing_msg_response()
            return

        switch, mode, debounce_close, debounce_open = msg.split(',')

        try:
            switch_obj = self.switches[int(switch, 16)]
        except IndexError:  # Neuron tracks 104 switches regardless of how many are connected
            return

        if (switch_obj.current_hw_config.mode != mode or
                switch_obj.current_hw_config.debounce_close != debounce_close or
                switch_obj.current_hw_config.debounce_open != debounce_open):
            switch_obj.send_config_to_switch()
        else:
            self.done_processing_msg_response()

    async def update_switches_from_hardware(self):
        """Process an SA: message and update switch states."""
        await self.send_and_wait_for_response_processed('SA:', 'SA:')

    def _process_sa(self, msg):
        if not self.platform.switches_initialized:
            return

        hw_states = {}
        _, raw_switch_data = msg.split(',')

        for offset, byte in enumerate(bytearray.fromhex(raw_switch_data)):
            for i in range(8):
                num = (offset * 8) + i
                if byte & (2**i):
                    hw_states[num] = 1
                else:
                    hw_states[num] = 0

        self.platform.hw_switch_data = hw_states
        self.update_switches_from_hw_data()
        self.done_processing_msg_response()

    def update_switches_from_hw_data(self):
        """Send the latest full switch dump (raw states) to the host."""
        self.host.sync_switch_states(self.platform, self.platform.hw_switch_data)
        self.platform.new_switch_data.set()  # Signal that we have new switch data

    def _process_switch_open(self, msg):
        """Process local switch open (logical state)."""
        self.host.switch_changed(self.platform, int(msg, 16), 0)

    def _process_switch_closed(self, msg):
        """Process local switch closed (logical state)."""
        self.host.switch_changed(self.platform, int(msg, 16), 1)

    def stopping(self):
        """Stop the Neuron processor and disable the watchdog."""
        self.send_and_forget('WD:1')
