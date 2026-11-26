"""Ball devices: a trough that ejects into a mechanical plunger lane, simulated as MPF's smart_virtual does."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.testing import GameRig, expect


def _plunger_lane(config):
    config["switches"]["s_shooter_lane"] = {"number": "20"}
    config["ball_devices"]["bd_trough"]["eject_targets"] = "bd_shooter_lane"
    config["ball_devices"]["bd_shooter_lane"] = {"ball_switches": "s_shooter_lane", "mechanical_eject": True}


@pytest.fixture
def game(tmp_path):
    rig = GameRig(basic_machine(tmp_path, edit=_plunger_lane))
    yield rig
    rig.stop()


def _shooter_lane(game):
    return game.machine.switches["s_shooter_lane"].state


def describe_a_plunger_lane():
    def it_starts_empty(game):  # only the trough starts with balls
        expect(_shooter_lane(game)).to_be_false()
        expect(game.machine.trough().balls).to_equal(3)

    def it_gets_the_ball_the_trough_ejects(game):
        game.start_game()
        game.advance(0.3)
        expect(game.machine.trough().balls).to_equal(2)
        expect(_shooter_lane(game)).to_be_true()

    def it_isnt_a_drain(game):  # it has no drain tag
        game.start_game()
        game.advance(0.3)
        expect(game.game.player.ball).to_equal(1)
        expect(game).not_to_have_posted("ball_drain")

    def it_shoots_a_waiting_ball_before_a_spec_drains_it(game):
        game.start_game()
        game.drain()
        expect(game.game.player.ball).to_equal(2)
        game.advance(0.3)
        expect(_shooter_lane(game)).to_be_true()   # ball 2 is waiting in the lane
        expect(game.machine.trough().balls).to_equal(2)

    def it_lets_the_player_shoot_the_ball(game):
        game.start_game()
        game.advance(0.3)
        game.machine.set_switch("s_shooter_lane", 0)   # plunged
        expect(game.machine.ball_devices["bd_shooter_lane"].balls).to_equal(0)


def describe_ball_device_config():
    @pytest.mark.parametrize(("edit", "message"), [
        (lambda c: c["ball_devices"]["bd_trough"].update(eject_targets="bd_nope"), "no ball device named 'bd_nope'"),
        (lambda c: c["ball_devices"].update(bd_lock={"ball_switches": "s_target"}), "plunger lanes"),
    ])
    def it_explains_a_mistake(tmp_path, edit, message):
        with pytest.raises(ConfigError, match=message):
            GameRig(basic_machine(tmp_path, edit=edit))
