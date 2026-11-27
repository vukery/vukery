"""The fast: net: section, as in MPF."""

import pytest

from vukery.core.errors import ConfigError
from vukery.platforms.fast.config import FastConfig, NetConfig, RgbConfig
from vukery.testing import expect

BOARDS = {"pf3208": {"model": "FP-I/O-3208", "order": 1}, "pf0804": {"model": "FP-I/O-0804", "order": 2}}


def describe_net_config():
    def it_lists_the_io_loop_boards_in_loop_order():
        config = NetConfig.from_yaml({"controller": "nano", "io_loop": BOARDS})
        expect(config.board_names_in_order()).to_equal(["pf3208", "pf0804"])

    def it_needs_the_board_order_to_have_no_gaps():
        with pytest.raises(ConfigError, match="sequential, starting at 1"):
            NetConfig.from_yaml({"controller": "nano", "io_loop": {"pf3208": {"model": "FP-I/O-3208", "order": 2}}})


def describe_unknown_settings():
    def it_names_them_in_fast():
        with pytest.raises(ConfigError, match="fast: unknown setting\\(s\\): colour"):
            FastConfig.from_yaml({"colour": "red"})

    def it_names_them_in_net():
        with pytest.raises(ConfigError, match="fast: net: unknown setting\\(s\\): colour"):
            NetConfig.from_yaml({"controller": "nano", "colour": "red"})

    def it_names_them_in_an_io_board():
        with pytest.raises(ConfigError, match="io_loop: pf3208: unknown setting\\(s\\): colour"):
            NetConfig.from_yaml({"controller": "nano",
                                 "io_loop": {"pf3208": {"model": "FP-I/O-3208", "order": 1, "colour": "red"}}})

    def it_names_them_in_rgb():
        with pytest.raises(ConfigError, match="fast: rgb: unknown setting\\(s\\): colour"):
            RgbConfig.from_yaml({"colour": "red"})

    def it_still_names_the_ports_vukery_doesnt_support():
        with pytest.raises(ConfigError, match="aren't supported by vukery yet: dmd"):
            FastConfig.from_yaml({"dmd": {}})
