# Copied from the Mission Pinball Framework (MPF) 0.57.6:
# https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/platforms/fast/communicators/rgb.py
# Copyright (c) The Mission Pinball Framework team and other contributors.
# MIT License: see vukery/_mpf/NOTICE.
"""RGB Board Serial Communicator.

Changes from MPF:
- Runs on the vukery host, with typed config (``led_hz`` is capped at 30 when
  the config is loaded, instead of here).
- ``MIN_FW`` is a class attribute, so the base class actually enforces it.
- With ``ignore_reboot`` (the default) a reboot is only logged. MPF also
  posted a ``fast_rgb_rebooted`` event; vukery has no event bus at this layer.
"""

from packaging import version

from vukery.platforms.fast.communicators.base import FastSerialCommunicator


class FastRgbCommunicator(FastSerialCommunicator):

    """Handles the serial communication for legacy FAST RGB processors.

    Includes the Nano Controller and FP-EXP-0800 LED controller.
    """

    MIN_FW = version.parse('0.87')
    IGNORED_MESSAGES = ['RX:P']

    def __init__(self, platform, processor, config):
        """Initialize the RGB platform and process boot message."""
        super().__init__(platform, processor, config)
        self.message_processors['!B:'] = self._process_boot_msg

    async def init(self):
        """Initialize the RGB processor and await an ID response."""
        # Loop here until we get a response
        await self.send_and_wait_for_response_processed('ID:', 'ID:', max_retries=-1)

    def _process_boot_msg(self, msg):
        """Process bootloader message."""
        self.log.debug("Got Bootloader message: !B:%s", msg)
        if msg in ('00', '02'):
            if self.config.ignore_reboot:
                self.log.error("FAST RGB processor rebooted. Ignoring.")
            else:
                self.log.error("FAST RGB processor rebooted.")
                self.host.stop("FAST RGB processor rebooted")

    def update_leds(self):
        """Update all the LEDs connected to the RGB processor of a FAST Nano controller.

        This is done once per game loop for efficiency (i.e. all LEDs are sent as a single
        update rather than lots of individual ones).
        """
        dirty_leds = [led for led in self.platform.fast_rgb_leds.values() if led.dirty]

        if dirty_leds:
            msg = 'RS:' + ','.join(["%s%s" % (led.number, led.current_color) for led in dirty_leds])
            self.send_and_forget(msg)

    def start_tasks(self):
        """Start listening for commands and schedule watchdog."""
        self.reset()
        self.tasks.append(self.host.schedule_interval(self.update_leds, 1 / self.config.led_hz))

    async def soft_reset(self, **kwargs):
        """Reset the NET processor."""
        del kwargs
        self.send_and_forget("RA:000000")

    def reset(self):
        """Reset the RGB processor."""
        self.send_and_forget('RA:000000')

    def stopping(self):
        """Stop the RGB processor and reset it."""
        self.reset()
