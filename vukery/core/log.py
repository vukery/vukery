"""Logging for vukery: one format, one file per environment, every component switchable.

- **Format** matches MPF's, so logs read the same:
  ``2026-11-25 21:04:10,651 : INFO : fast.net : Connected to FP-CPU-002-2 with firmware v01.05``
- **One file per environment** (``log/development.log``, ``log/production.log``),
  appended to on every run after a separator line and rotated by size. Not a new
  timestamped file per run like MPF.
- **Every component logs under a dotted name** (``fast.net``, ``fast.switch``,
  ``devices.coil.c_test``, ``modes.hole_score``…). A level set on a name applies to
  everything under it, so ``fast: debug`` turns on all FAST logging and
  ``fast.rgb: off`` silences just the RGB port. There's no other on/off mechanism:
  MPF's per-component ``debug: true`` keys are accepted and mean the same as setting
  that component to ``debug`` here.

``VUK_LOG`` sets one level for everything on the fly, overriding the whole
``logging:`` config (like Rails' log level)::

    VUK_LOG=debug vuk run

Levels: debug, info, warning, error. Per-component levels only come from the
``logging:`` config section::


    logging:
      level: info        # default for everything
      console: info      # the most detail the console shows
      file: debug        # the most detail the log file gets
      components:        # per component; children inherit
        fast: debug
        fast.rgb: off
        events: warning
"""

import logging
import logging.handlers
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from vukery.core.errors import ConfigError

ROOT = "vukery"
FORMAT = "%(asctime)s : %(levelname)s : %(name)s : %(message)s"
OFF = logging.CRITICAL + 10  # above everything vukery logs

VUK_LOG_LEVELS = ("debug", "info", "warning", "error")

LEVELS = {
    "off": OFF,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


def parse_level(value: Any, where: str) -> int:
    match value:
        case bool():  # YAML turns a bare `off` into False and `on` into True
            return logging.DEBUG if value else OFF
        case str() if value.lower() in LEVELS:
            return LEVELS[value.lower()]
        case _:
            raise ConfigError(f"logging: {where}: level must be one of {', '.join(LEVELS)}, got {value!r}")


class _ShortNames(logging.Filter):
    """Show ``fast.net`` instead of ``vukery.fast.net`` in output."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name.startswith(ROOT + "."):
            record.name = record.name[len(ROOT) + 1:]
        return True


@dataclass(frozen=True)
class LoggingConfig:
    level: int = logging.INFO
    console: int = logging.INFO
    file: int = logging.DEBUG
    components: Mapping[str, int] = field(default_factory=dict[str, int])
    max_file_mb: int = 10
    backups: int = 5

    @classmethod
    def from_yaml(cls, data: Mapping[str, Any] | None) -> LoggingConfig:
        data = data or {}
        unknown = sorted(set(data) - {"level", "console", "file", "components", "max_file_mb", "backups"})
        if unknown:
            raise ConfigError(f"logging: unknown setting(s): {', '.join(unknown)}")
        return cls(
            level=parse_level(data.get("level", "info"), "level"),
            console=parse_level(data.get("console", "info"), "console"),
            file=parse_level(data.get("file", "debug"), "file"),
            components={str(name): parse_level(level, f"components: {name}")
                        for name, level in (data.get("components") or {}).items()},
            max_file_mb=int(data.get("max_file_mb", 10)),
            backups=int(data.get("backups", 5)),
        )

    def with_vuk_log(self, value: str | None) -> LoggingConfig:
        """Apply a ``VUK_LOG`` level: it overrides every setting, components included.

        Per-component levels only come from the ``logging:`` config.
        """
        if not value or not value.strip():
            return self
        match value.strip().lower():
            case "debug" | "info" | "warning" | "error" as name:
                level = LEVELS[name]
            case _:
                raise ConfigError(f"VUK_LOG must be one of {', '.join(VUK_LOG_LEVELS)}, got {value!r}. "
                                  "Per-component levels go in the logging: config.")
        return LoggingConfig(level, level, level, {}, self.max_file_mb, self.backups)


def get_logger(name: str) -> logging.Logger:
    """The logger for a component, e.g. ``get_logger("fast.net")``."""
    return logging.getLogger(f"{ROOT}.{name}")


def setup_logging(config: LoggingConfig, environment: str, log_dir: Path | None = None,
                  console: bool = True) -> None:
    """Configure vukery's loggers. ``log_dir=None`` means no file (the test environment)."""
    root = logging.getLogger(ROOT)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.propagate = False
    root.setLevel(config.level)

    # Reset every vukery logger first, so removing a component from config turns it back to the default
    for name, logger in logging.root.manager.loggerDict.items():
        if name.startswith(ROOT + ".") and isinstance(logger, logging.Logger):
            logger.setLevel(logging.NOTSET)
    for name, level in config.components.items():
        get_logger(name).setLevel(level)

    formatter = logging.Formatter(FORMAT)
    short_names = _ShortNames()

    if console:
        stream = logging.StreamHandler()
        stream.setLevel(config.console)
        stream.setFormatter(formatter)
        stream.addFilter(short_names)
        root.addHandler(stream)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"{environment}.log"
        file = logging.handlers.RotatingFileHandler(
            path, maxBytes=config.max_file_mb * 1024 * 1024, backupCount=config.backups, encoding="utf-8")
        file.setLevel(config.file)
        file.setFormatter(formatter)
        file.addFilter(short_names)
        root.addHandler(file)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"\n===== vukery started {datetime.now():%Y-%m-%d %H:%M:%S} ({environment}) =====\n")


class Logs:
    """Mix-in that gives a class a component logger.

    Stands in for MPF's ``LogMixin`` (the ``debug_log`` / ``info_log`` / … methods
    that code copied from MPF calls).
    """

    log: logging.Logger

    def configure_logging(self, name: str, debug: bool = False) -> None:
        """Use the logger for component ``name``. ``debug=True`` is MPF's ``debug: true``."""
        self.log = get_logger(name)
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
