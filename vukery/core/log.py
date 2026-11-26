"""Logging helpers for vukery components.

A small stand-in for MPF's ``LogMixin``: a named logger plus the
``debug_log`` / ``info_log`` / ``warning_log`` / ``error_log`` methods that
hardware code copied from MPF calls.
"""

import logging


class Logs:
    """Mix-in that gives a class a named logger."""

    log: logging.Logger

    def configure_logging(self, name: str, debug: bool = False) -> None:
        self.log = logging.getLogger(name)
        if debug:
            self.log.setLevel(logging.DEBUG)

    def debug_log(self, msg: str, *args: object) -> None:
        self.log.debug(msg, *args)

    def info_log(self, msg: str, *args: object) -> None:
        self.log.info(msg, *args)

    def warning_log(self, msg: str, *args: object) -> None:
        self.log.warning(msg, *args)

    def error_log(self, msg: str, *args: object) -> None:
        self.log.error(msg, *args)
