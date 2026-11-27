"""Switches: config, state, events, and handlers for a switch held down."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.core.switches import SwitchConfig
from vukery.testing import GameRig, expect

HELD = '''
    from vukery import Mode, on


    class Held(Mode):
        start_on = "ball_started"

        @on.switch("s_target", hold=2)         # MPF: a switch handler with ms:
        def held(self):
            self.player.held = self.player.get("held", 0) + 1

        @on.switch("s_target", state="inactive")
        def released(self):
            self.player.released = self.player.get("released", 0) + 1
'''


@pytest.fixture
def game(tmp_path):
    folder = basic_machine(tmp_path, edit=lambda c: c["modes"].append("held"), files={"modes/held/mode.py": HELD})
    rig = GameRig(folder)
    rig.start_game()
    yield rig
    rig.stop()


def describe_switches():
    def describe_config():
        def it_rejects_settings_it_doesnt_know():
            with pytest.raises(ConfigError, match="unknown setting"):
                SwitchConfig.from_yaml("s_x", {"number": "1", "colour": "red"})

        def it_takes_no_or_nc():
            with pytest.raises(ConfigError, match="type must be NO or NC"):
                SwitchConfig.from_yaml("s_x", {"number": "1", "type": "maybe"})

        def it_reads_a_bare_no_as_normally_open():   # YAML turns an unquoted NO into false
            expect(SwitchConfig.from_yaml("s_x", {"number": "1", "type": False}).type).to_equal("NO")

        def it_takes_nc_in_any_case():
            expect(SwitchConfig.from_yaml("s_x", {"number": "1", "type": "nc"}).type).to_equal("NC")

        def it_rejects_a_name_it_doesnt_know(game):
            with pytest.raises(ConfigError, match="no switch named 's_nope'"):
                game.machine.switches["s_nope"]

    def describe_held_down():
        def it_runs_a_hold_handler_once_the_switch_has_been_held_that_long(game):
            game.switch("s_target", state="active")
            game.advance(1.9)
            expect(game.player.get("held", 0)).to_equal(0)
            game.advance(0.2)
            expect(game.player.held).to_equal(1)

        def it_doesnt_run_it_if_the_switch_opens_first(game):
            game.switch("s_target", state="active")
            game.advance(1)
            game.switch("s_target", state="inactive")
            game.advance(5)
            expect(game.player.get("held", 0)).to_equal(0)
            expect(game.player.released).to_equal(1)

        def it_holds_with_game_switch_hold(game):  # the rig's own way: press, wait, release
            game.switch("s_target", hold=2.5)
            expect(game.player.held).to_equal(1)

        def it_knows_how_long_a_switch_has_been_active(game):
            game.switch("s_target", state="active")
            game.advance(3)
            expect(game.machine.switches.is_active("s_target", seconds=2)).to_equal(True)
            expect(game.machine.switches.is_active("s_target", seconds=5)).to_equal(False)
            expect(game.switches("s_target")).to_be_active()

        def it_counts_a_switch_still_held_when_the_mode_starts_again(game):
            game.switch("s_target", state="active")
            game.drain()  # the ball ends with the target held; the next ball starts the mode again
            game.advance(3)
            expect(game.player.held).to_equal(1)  # timed from when it was pressed, on the earlier ball

        def it_drops_the_handler_when_the_mode_stops(game):
            game.switch("s_target", state="active")
            game.drain()
            game.drain()
            game.drain()  # game over: the mode is stopped for good
            expect(game.machine.switches._timed).to_equal([])

    def describe_events_from_config():
        def it_posts_events_when_activated_and_deactivated(tmp_path):
            def edit(config):
                config["switches"]["s_target"]["events_when_activated"] = "target_down"
                config["switches"]["s_target"]["events_when_deactivated"] = "target_up"

            rig = GameRig(basic_machine(tmp_path, edit=edit))
            try:
                rig.switch("s_target")
                expect(rig).to_have_posted("target_down", times=1)
                expect(rig).to_have_posted("target_up", times=1)
            finally:
                rig.stop()
