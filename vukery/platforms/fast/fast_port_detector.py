# Copied from the Mission Pinball Framework (MPF) 0.57.6:
# https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/platforms/fast/fast_port_detector.py
# Copyright (c) The Mission Pinball Framework team and other contributors.
# MIT License: see vukery/_mpf/NOTICE.
"""Scan serial connections and request ID: to identify FAST hardware.

Changes from MPF:
- Ports are listed and opened through the vukery host
  (``host.list_serial_ports`` / ``host.open_serial``), so tests can fake them.
- Returns ``{processor: port}`` instead of writing into the platform's config.
- A port that can't be opened is logged and skipped.
"""

import asyncio

from vukery.platforms.fast.fast_defines import USB_IDS


class FastPortDetector:

    """Class for detecting FAST platform hardware on connected serial ports."""

    ATTEMPTS = 5
    TIMEOUT = 1.0  # seconds to wait for each ID: response

    def __init__(self, platform, autodetect_processors, hardcoded_ports, bauds):
        """Initialize the port detector.

        bauds: {processor: baud} for the processors being detected.
        """
        self.platform = platform
        self.host = platform.host
        self.autodetect_processors = autodetect_processors
        self.hardcoded_ports = hardcoded_ports
        self.bauds = bauds
        self.detected_fast_ports = list()  # tuples of (port, baud)
        self.tasks = list()
        self.open_ports = dict()  # task: open SerialPort
        self.results = dict()  # dict of processor: port

        self.platform.log.info("Auto-detecting ports for the following connections: %s", self.autodetect_processors)
        self._find_fast_devices()

    def _find_fast_devices(self):
        # Creates a list of all serial ports which have devices attached which match
        # USB VID/PID combinations of FAST devices we're looking for.
        for port in self.host.list_serial_ports():
            if (port.vid, port.pid) in USB_IDS:
                proc, desc = USB_IDS[(port.vid, port.pid)]
                # A Nano is one USB device with four serial ports (all listed as 'net'), and
                # one of them is the RGB port, so check every FAST port for every wanted processor.
                if proc in self.autodetect_processors or proc == 'net':
                    baud = self.bauds.get(proc) or next(iter(self.bauds.values()))
                    if port.device not in self.hardcoded_ports:
                        self.detected_fast_ports.append((port.device, baud))
                        self.platform.log.debug("Port %s is connected to a %s.", port.device, desc)
                    else:
                        self.platform.log.debug(
                            "Skipping auto-detect of %s on %s since it's in the config file elsewhere.",
                            proc, port.device)

    async def detect_ports(self):
        """Query the available serial ports for an ID: response. Returns {processor: port}."""
        self.tasks = [asyncio.ensure_future(self._connect_task(port, baud)) for port, baud in self.detected_fast_ports]

        for task in self.tasks:
            task.add_done_callback(self._cleanup_port)

        # Cancelled tasks are expected (the rest are cancelled once everything is found)
        await asyncio.gather(*self.tasks, return_exceptions=True)
        return self.results

    async def _connect_task(self, port, baud):
        """One instance per port is launched to connect and ID whatever's on the other end.

        Sends an ID: command once per second until it gets a response or until other tasks have
        found all the ports and the remaining ones are cancelled.

        If an ID: response comes back that matches a processor we're looking for,
        it reports success and ends.
        """
        try:
            serial = await self.host.open_serial(port, baud)
        except OSError as e:
            self.platform.log.error("Could not connect to port %s (%s). Is another program using it?", port, e)
            return

        self.platform.debug_log(" - success connecting to port %s", port)
        self.open_ports[asyncio.current_task()] = serial

        for _ in range(self.ATTEMPTS):
            serial.write(b'ID:\r')

            try:
                data = await asyncio.wait_for(serial.read(100), timeout=self.TIMEOUT)
            except asyncio.TimeoutError:
                data = None

            if data:
                data = data.decode('utf-8', errors='ignore')
                for processor in self.autodetect_processors:
                    if processor not in self.results and processor.upper() in data:
                        self._report_success(processor, port)
                        return

        self.platform.debug_log("Unable to get ID: on port %s after %s retries.", port, self.ATTEMPTS)

    def _report_success(self, processor, port):
        self.results[processor] = port
        self.platform.log.info('Detected %s on port %s', processor.upper(), port)

        if len(self.results) >= len(self.autodetect_processors):
            self._cancel_remaining_tasks()

    def _cancel_remaining_tasks(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()

    def _cleanup_port(self, task):
        serial = self.open_ports.pop(task, None)
        if serial:
            serial.close()
