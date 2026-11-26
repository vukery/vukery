"""The light stack (MPF's priorities and keys) and light groups."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.testing import GameRig

RED, GREEN, BLUE, BLACK = (255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0)


def _lights(config):
    config["lights"] = {f"l_lane_{i}": {"number": str(10 + i)} for i in range(1, 4)} | config["lights"]
    config["light_groups"] = {"lanes": "l_lane_1, l_lane_2, l_lane_3"}


@pytest.fixture
def rig(tmp_path):
    game = GameRig(basic_machine(tmp_path, edit=_lights))
    yield game
    game.stop()


def describe_the_light_stack():
    def it_shows_the_highest_priority(rig):
        light = rig.machine.lights["l_lane_1"]
        light.color("ff0000")                           # priority 0, no key
        light.color("00ff00", priority=10, key="show")
        assert light.current_color() == GREEN
        light.color("0000ff", priority=5, key="mode")  # lower: saved, not shown
        assert light.current_color() == GREEN

    def it_reveals_whats_underneath_when_a_key_is_removed(rig):
        light = rig.machine.lights["l_lane_1"]
        light.color("ff0000")
        light.color("00ff00", priority=10, key="show")
        light.color("0000ff", priority=5, key="mode")
        light.remove("show")
        assert light.current_color() == BLUE
        light.remove("mode")
        assert light.current_color() == RED

    def it_replaces_an_entry_with_the_same_key(rig):
        light = rig.machine.lights["l_lane_1"]
        light.color("ff0000", priority=10, key="show")
        light.color("00ff00", priority=10, key="show")
        assert (light.current_color(), len(light.stack)) == (GREEN, 1)

    def it_shows_the_latest_on_a_tie(rig):
        light = rig.machine.lights["l_lane_1"]
        light.color("ff0000", priority=10, key="a")
        light.color("00ff00", priority=10, key="b")
        assert light.current_color() == GREEN

    def it_is_off_with_nothing_on_the_stack(rig):
        light = rig.machine.lights["l_lane_1"]
        light.color("ff0000", key="only")
        light.remove("only")
        assert light.current_color() == BLACK

    def it_fades_to_whats_underneath(rig):
        light = rig.machine.lights["l_lane_1"]
        light.color("000000")
        light.color("ffffff", priority=10, key="show")
        light.remove("show", fade_ms=1000)
        rig.advance(0.5)
        assert light.current_color() == (128, 128, 128)

    def it_ignores_removing_a_key_that_isnt_there(rig):
        light = rig.machine.lights["l_lane_1"]
        light.color("ff0000")
        light.remove("nothing")
        assert light.current_color() == RED


def describe_light_groups():
    def it_keeps_its_lights_in_order(rig):
        group = rig.machine.light_groups["lanes"]
        assert [light.name for light in group] == ["l_lane_1", "l_lane_2", "l_lane_3"]
        assert (len(group), group[1].name) == (3, "l_lane_2")

    def it_colors_every_light_in_it(rig):
        group = rig.machine.light_groups["lanes"]
        group.color("ff0000", priority=10, key="show")
        assert [light.current_color() for light in group] == [RED, RED, RED]
        group.remove("show")
        assert [light.current_color() for light in group] == [BLACK, BLACK, BLACK]

    def it_turns_them_on_and_off(rig):
        group = rig.machine.light_groups["lanes"]
        group.on()
        assert group[0].current_color() == (255, 255, 255)
        group.off()
        assert group[2].current_color() == BLACK

    @pytest.mark.parametrize(("groups", "message"), [
        ({"lanes": "l_lane_1, l_nope"}, "no light named l_nope"),
        ({"l_frenzy": "l_lane_1"}, "already a light with that name"),
        ({"lanes": []}, "list its lights"),
    ])
    def it_explains_a_group_it_cant_make(tmp_path, groups, message):
        def edit(config):
            _lights(config)
            config["light_groups"] = groups

        with pytest.raises(ConfigError, match=message):
            GameRig(basic_machine(tmp_path, edit=edit))
