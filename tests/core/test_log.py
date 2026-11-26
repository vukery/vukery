"""Logging: MPF's format, one file per environment, and on/off switches for every component."""

import logging
import re

import pytest
import yaml

from vukery.core.errors import ConfigError
from vukery.core.log import LoggingConfig, Logs, get_logger, setup_logging

MPF_LINE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} : (DEBUG|INFO|WARNING|ERROR) : [\w.]+ : .+$")


def config(text: str = "") -> LoggingConfig:
    return LoggingConfig.from_yaml(yaml.safe_load(text) or {})


@pytest.fixture
def log_file(tmp_path):
    def read() -> str:
        for handler in logging.getLogger("vukery").handlers:
            handler.flush()
        return (tmp_path / "development.log").read_text()

    read.dir = tmp_path
    yield read
    setup_logging(LoggingConfig(), "test", log_dir=None, console=False)


def describe_logging():
    def describe_the_log_file():
        def it_uses_mpfs_line_format(log_file):
            setup_logging(config(), "development", log_file.dir, console=False)
            get_logger("fast.net").info("Connected to FP-CPU-002-2 with firmware v01.05")
            lines = [line for line in log_file().splitlines() if " : " in line]
            assert lines and all(MPF_LINE.match(line) for line in lines)
            assert " : INFO : fast.net : Connected to FP-CPU-002-2" in lines[-1]

        def it_appends_every_run_to_one_file_per_environment(log_file):
            setup_logging(config(), "development", log_file.dir, console=False)
            get_logger("game").info("first run")
            setup_logging(config(), "development", log_file.dir, console=False)
            get_logger("game").info("second run")
            text = log_file()
            assert text.count("===== vukery started") == 2
            assert "first run" in text and "second run" in text
            assert [p.name for p in log_file.dir.iterdir()] == ["development.log"]

    def describe_turning_components_on_and_off():
        def it_turns_on_a_whole_area(log_file):
            setup_logging(config("level: info\ncomponents: {fast: debug}"), "development", log_file.dir,
                          console=False)
            get_logger("fast.net").debug("net detail")
            get_logger("fast.switch").debug("switch detail")
            get_logger("game").debug("game detail")
            text = log_file()
            assert "net detail" in text and "switch detail" in text
            assert "game detail" not in text

        def it_silences_one_component_inside_an_area(log_file):
            setup_logging(config("components: {fast: debug, fast.rgb: off}"), "development", log_file.dir,
                          console=False)
            get_logger("fast.rgb").error("rgb error")
            get_logger("fast.net").debug("net detail")
            text = log_file()
            assert "rgb error" not in text
            assert "net detail" in text

        def it_accepts_a_bare_yaml_off(log_file):
            # YAML reads `fast: off` as False
            setup_logging(config("components:\n  fast: off"), "development", log_file.dir, console=False)
            get_logger("fast.net").error("hidden")
            assert "hidden" not in log_file()

        def it_resets_components_removed_from_config(log_file):
            setup_logging(config("components: {fast: off}"), "development", log_file.dir, console=False)
            setup_logging(config(), "development", log_file.dir, console=False)
            get_logger("fast.net").info("back on")
            assert "back on" in log_file()

        def it_applies_vuk_log(log_file):
            base = config("level: warning")
            setup_logging(base.with_vuk_log("debug"), "development", log_file.dir, console=False)
            get_logger("events").debug("event detail")
            get_logger("game").debug("game detail")
            text = log_file()
            assert "event detail" in text and "game detail" in text

        def it_honors_mpfs_debug_true(log_file):
            setup_logging(config("level: info"), "development", log_file.dir, console=False)

            class Component(Logs):
                def __init__(self):
                    self.configure_logging("fast.net", debug=True)

            Component().debug_log("from debug: true")
            assert "from debug: true" in log_file()

        def it_keeps_the_file_more_detailed_than_the_console(log_file):
            cfg = config("level: debug\nconsole: warning\nfile: debug")
            assert cfg.console == logging.WARNING and cfg.file == logging.DEBUG

    def describe_vuk_log():
        def it_overrides_every_setting_with_one_level():
            cfg = config("level: warning\nconsole: error\nfile: info\ncomponents: {fast: off, events: debug}")
            cfg = cfg.with_vuk_log("debug")
            assert (cfg.level, cfg.console, cfg.file) == (logging.DEBUG,) * 3
            assert cfg.components == {}

        def it_accepts_only_four_levels():
            for name in ("debug", "INFO", "warning", "error"):
                config().with_vuk_log(name)
            for bad in ("fatal", "off", "fast=debug"):
                with pytest.raises(ConfigError, match="VUK_LOG must be one of"):
                    config().with_vuk_log(bad)

        def it_ignores_an_empty_value():
            cfg = config()
            assert cfg.with_vuk_log("") is cfg and cfg.with_vuk_log(None) is cfg

    def describe_config_errors():
        def it_rejects_unknown_levels():
            with pytest.raises(ConfigError, match="level must be one of"):
                config("components: {fast: loud}")

        def it_rejects_unknown_settings():
            with pytest.raises(ConfigError, match="unknown setting"):
                config("debug: true")
