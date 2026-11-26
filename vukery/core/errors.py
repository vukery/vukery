"""Errors raised by vukery."""


class VukeryError(Exception):
    """Base class for vukery errors."""


class ConfigError(VukeryError):
    """The machine config is invalid."""


class HardwareError(VukeryError):
    """Hardware reported a problem, or doesn't match the config."""


class CoilLimitError(VukeryError):
    """A coil was asked to do something outside its configured limits."""
