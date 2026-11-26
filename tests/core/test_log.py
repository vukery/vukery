"""Logging: MPF's format, one file per environment, and on/off switches for every component."""

import logging
import re

import pytest
import yaml

from vukery.core.errors import ConfigError
from vukery.core.log import LoggingConfig, Logs, get_logger, setup_logging
from vukery.testing import expect

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
            expect(lines and all(MPF_LINE.match(line) for line in lines)).to_be_true()
            expect(lines[-1]).to_contain(" : INFO : fast.net : Connected to FP-CPU-002-2")

        def it_appends_every_run_to_one_file_per_environment(log_file):
            setup_logging(config(), "development", log_file.dir, console=False)
            get_logger("game").info("first run")
            setup_logging(config(), "development", log_file.dir, console=False)
            get_logger("game").info("second run")
            text = log_file()
            expect(text.count("===== vukery started")).to_equal(2)
            expect(text).to_contain("first run")
            expect(text).to_contain("second run")
            expect([p.name for p in log_file.dir.iterdir()]).to_equal(["development.log"])

    def describe_turning_components_on_and_off():
        def it_turns_on_a_whole_area(log_file):
            setup_logging(config("level: info\ncomponents: {fast: debug}"), "development", log_file.dir,
                          console=False)
            get_logger("fast.net").debug("net detail")
            get_logger("fast.switch").debug("switch detail")
            get_logger("game").debug("game detail")
            text = log_file()
            expect(text).to_contain("net detail")
            expect(text).to_contain("switch detail")
            expect(text).not_to_contain("game detail")

        def it_silences_one_component_inside_an_area(log_file):
            setup_logging(config("components: {fast: debug, fast.rgb: off}"), "development", log_file.dir,
                          console=False)
            get_logger("fast.rgb").error("rgb error")
            get_logger("fast.net").debug("net detail")
            text = log_file()
            expect(text).not_to_contain("rgb error")
            expect(text).to_contain("net detail")

        def it_accepts_a_bare_yaml_off(log_file):
            # YAML reads `fast: off` as False
            setup_logging(config("components:\n  fast: off"), "development", log_file.dir, console=False)
            get_logger("fast.net").error("hidden")
            expect(log_file()).not_to_contain("hidden")

        def it_resets_components_removed_from_config(log_file):
            setup_logging(config("components: {fast: off}"), "development", log_file.dir, console=False)
            setup_logging(config(), "development", log_file.dir, console=False)
            get_logger("fast.net").info("back on")
            expect(log_file()).to_contain("back on")

        def it_applies_vuk_log(log_file):
            base = config("level: warning")
            setup_logging(base.with_vuk_log("debug"), "development", log_file.dir, console=False)
            get_logger("events").debug("event detail")
            get_logger("game").debug("game detail")
            text = log_file()
            expect(text).to_contain("event detail")
            expect(text).to_contain("game detail")

        def it_honors_mpfs_debug_true(log_file):
            setup_logging(config("level: info"), "development", log_file.dir, console=False)

            class Component(Logs):
                def __init__(self):
                    self.configure_logging("fast.net", debug=True)

            Component().debug_log("from debug: true")
            expect(log_file()).to_contain("from debug: true")

        def it_keeps_the_file_more_detailed_than_the_console(log_file):
            cfg = config("level: debug\nconsole: warning\nfile: debug")
            expect(cfg.console).to_equal(logging.WARNING)
            expect(cfg.file).to_equal(logging.DEBUG)

    def describe_vuk_log():
        def it_overrides_every_setting_with_one_level():
            cfg = config("level: warning\nconsole: error\nfile: info\ncomponents: {fast: off, events: debug}")
            cfg = cfg.with_vuk_log("debug")
            expect((cfg.level, cfg.console, cfg.file)).to_equal((logging.DEBUG,) * 3)
            expect(cfg.components).to_equal({})

        def it_accepts_only_four_levels():
            for name in ("debug", "INFO", "warning", "error"):
                config().with_vuk_log(name)
            for bad in ("fatal", "off", "fast=debug"):
                with pytest.raises(ConfigError, match="VUK_LOG must be one of"):
                    config().with_vuk_log(bad)

        def it_ignores_an_empty_value():
            cfg = config()
            expect(cfg.with_vuk_log("")).to_equal(cfg)
            expect(cfg.with_vuk_log(None)).to_equal(cfg)

    def describe_config_errors():
        def it_rejects_unknown_levels():
            with pytest.raises(ConfigError, match="level must be one of"):
                config("components: {fast: loud}")

        def it_rejects_unknown_settings():
            with pytest.raises(ConfigError, match="unknown setting"):
                config("debug: true")
