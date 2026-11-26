# Copied from the Mission Pinball Framework (MPF) 0.57.6:
# https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/platforms/fast/fast_io_board.py
# Copyright (c) The Mission Pinball Framework team and other contributors.
# MIT License: see vukery/_mpf/NOTICE.
"""FAST I/O Board."""

from vukery.core.errors import HardwareError
from vukery.platforms.fast.fast_defines import VALID_IO_BOARDS


class FastIoBoard:

    """A FAST I/O board on the NET processor."""

    # pylint: disable-msg=too-many-arguments
    def __init__(self, communicator, name, node_id, model_string, firmware_version,
                 switch_count, driver_count, prior_switches, prior_drivers):
        """Initialize FastIoBoard."""
        self.communicator = communicator
        self.name = str(name)
        self.node_id = node_id  # position in the I/O loop, 0-indexed
        self.model = model_string
        self.firmware_version = firmware_version
        self.start_switch = prior_switches
        self.start_driver = prior_drivers
        self.switch_count = switch_count
        self.driver_count = driver_count

        if self.model not in VALID_IO_BOARDS:
            raise HardwareError(f"Invalid I/O board model: {self.model}")

    def __repr__(self):
        """Return representation of this I/O board."""
        return f'{self.model} "{self.name}"'

    def get_description_string(self) -> str:
        """Return description string."""
        return f"Board {self.node_id} - Model: {self.model}, Firmware: {self.firmware_version}, " + \
            f"Switches: {self.switch_count}, Drivers: {self.driver_count}"
