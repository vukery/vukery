"""Lights: colors, channel orders, RGBW and fades, on the simulated platform."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.devices.light import LightConfig, parse_color
from vukery.testing import GameRig


def _rig(tmp_path, lights):
    def edit(config):
        config["lights"] = lights
        config.pop("dashboard", None)

    return GameRig(basic_machine(tmp_path, edit=edit, files={"config/dashboard.yaml": "dashboard: {}\n",
                                                             "modes/frenzy/mode.py": '''
        from vukery import Mode


        class Frenzy(Mode):
            start_on = "never"
    '''}))


def _channel(rig, number):
    return rig.machine.platform.lights[number].brightness


def describe_lights():
    def describe_colors():
        @pytest.mark.parametrize("value", ["ff8800", (255, 136, 0), [255, 136, 0]])
        def it_takes_hex_or_three_numbers(value):
            assert parse_color(value) == (255, 136, 0)

        @pytest.mark.parametrize(("value", "message"), [("ff88zz", "Not a color"), ((300, 0, 0), "0-255"),
                                                        ("orange", "Not a color")])
        def it_explains_a_bad_color(value, message):
            with pytest.raises(ConfigError, match=message):
                parse_color(value)

    def describe_channels():
        def it_maps_a_grb_light_in_that_order(tmp_path):
            rig = _rig(tmp_path, {"l_x": {"number": "7", "type": "grb"}})
            try:
                rig.machine.lights["l_x"].color("ff0000")  # red
                assert (_channel(rig, "7-0"), _channel(rig, "7-1"), _channel(rig, "7-2")) == (0.0, 1.0, 0.0)
            finally:
                rig.stop()

        def it_continues_a_light_from_the_previous_one(tmp_path):
            rig = _rig(tmp_path, {"l_a": {"number": "1", "type": "rgb"},
                                  "l_b": {"previous": "l_a", "type": "rgb"}})
            try:
                rig.machine.lights["l_b"].color("0000ff")
                assert _channel(rig, "2-2") == 1.0  # l_a is 1-0..1-2, so l_b starts at 2-0
            finally:
                rig.stop()

        def it_splits_white_out_of_an_rgbw_light(tmp_path):
            rig = _rig(tmp_path, {"l_w": {"start_channel": "5-0", "type": "rgbw"}})
            try:
                rig.machine.lights["l_w"].color("ffffff")  # all white: the white channel only
                channels = [_channel(rig, n) for n in ("5-0", "5-1", "5-2", "6-0")]
                assert channels == [0.0, 0.0, 0.0, 1.0]
            finally:
                rig.stop()

        @pytest.mark.parametrize(("lights", "message"), [
            ({"l_x": {"previous": "l_x", "type": "rgb"}}, "can't refer to itself"),
            ({"l_x": {"previous": "l_later", "type": "rgb"}}, "must be defined first"),
            ({"l_x": {"number": "1", "type": "rgbw"}}, "doesn't match its 3 channels"),
            ({"l_x": {"number": "1", "type": "rgx"}}, "invalid letter 'x'"),
            ({"l_x": {"start_channel": "1-0"}}, "need a type"),
            ({"l_x": {"type": "rgb"}}, "needs a number"),
            ({"l_x": {"number": "1", "channels": {"red": {"number": "2-0"}}}}, "both number and channels"),
        ])
        def it_explains_a_light_it_cant_map(tmp_path, lights, message):
            with pytest.raises(ConfigError, match=message):
                _rig(tmp_path, lights)

        def it_rejects_settings_it_doesnt_know():
            with pytest.raises(ConfigError, match="unknown setting"):
                LightConfig.from_yaml("l_x", {"number": "1", "colour": "red"})

    def describe_fades():
        def it_is_partway_there_partway_through_a_fade(tmp_path):
            rig = _rig(tmp_path, {"l_x": {"number": "3"}})
            try:
                light = rig.machine.lights["l_x"]
                light.color("ffffff", fade_ms=1000)
                rig.advance(0.5)
                assert light.current_color() == (128, 128, 128)
                assert _channel(rig, "3-0") == pytest.approx(0.5, abs=0.01)
                rig.advance(0.6)
                assert light.current_color() == (255, 255, 255)
            finally:
                rig.stop()
