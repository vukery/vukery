"""Tilt (an optional built-in mode, MPF's tilt): warnings, a tilted ball, slam tilt, settling, the look.

The scenarios follow MPF's test_Tilt.py.
"""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.testing import GameRig, expect

SWITCHES = {
    "s_plumb_bob": {"number": "40", "tags": "tilt_warning"},
    "s_tilt": {"number": "41", "tags": "tilt"},
    "s_slam": {"number": "42", "tags": "slam_tilt"},
}


def _with_tilt(config):
    config["switches"] |= SWITCHES
    config["modes"] = [*config["modes"], "tilt"]


def _rig(tmp_path, files=None, example="basic"):
    return GameRig(basic_machine(tmp_path, edit=_with_tilt, files=files, example=example))


@pytest.fixture
def game(tmp_path):
    rig = _rig(tmp_path)
    yield rig
    rig.stop()


def _player(game):
    return game.game.player


def describe_tilt():
    def it_only_runs_when_the_game_lists_it(tmp_path):
        rig = GameRig(basic_machine(tmp_path))
        try:
            expect("tilt" in rig.machine.modes.modes).to_be_false()
        finally:
            rig.stop()

    def it_runs_between_games_too(game):  # to catch a slam tilt any time
        expect(game.mode("tilt")).to_be_running()

    def describe_a_tilted_ball():  # MPF: test_simple_tilt
        def it_ends_the_ball_and_stops_scoring(game):
            game.start_game(players=2)
            game.switch("s_target")
            expect(_player(game).score).to_equal(1000)
            game.switch("s_tilt")
            expect(game).to_have_posted("tilt", times=1)
            expect(game.game.tilted).to_be_true()
            expect(game.machine.flippers["left_flipper"].enabled).to_be_false()
            game.switch("s_target")
            expect(_player(game).score).to_equal(1000)              # no scoring while tilted

        def it_waits_for_the_ball_then_clears_and_starts_the_next(game):
            game.start_game(players=2)
            game.switch("s_tilt")
            expect(game.game.player.number).to_equal(1)              # held until the ball is back
            game.drain()
            expect(game).to_have_posted("tilt_clear", times=1)
            expect(game.game.tilted).to_be_false()
            expect(game.game.player.number).to_equal(2)

        def it_still_plays_an_extra_ball(game):  # MPF: test_tilt_with_extra_ball
            game.start_game()
            _player(game).extra_balls = 1
            game.switch("s_tilt")
            game.drain()
            expect(_player(game).ball).to_equal(1)                   # the extra ball, same ball number
            expect(game).to_have_posted("ball_started", times=2)

        def it_ignores_a_tilt_between_games(game):
            game.switch("s_tilt")
            expect(game).not_to_have_posted("tilt")

    def describe_warnings():  # MPF: test_tilt_warning
        def it_warns_then_tilts_on_the_last_one(game):
            game.start_game()
            game.switch("s_plumb_bob")
            expect(game).to_have_posted("tilt_warning_1", times=1)
            game.advance(1)
            game.switch("s_plumb_bob")
            expect(game).to_have_posted("tilt_warning_2", times=1)
            expect(_player(game).tilt_warnings).to_equal(2)
            game.advance(1)
            game.switch("s_plumb_bob")
            expect(game).to_have_posted("tilt", times=1)
            expect(game).not_to_have_posted("tilt_warning_3")

        def it_counts_one_warning_for_a_bob_that_swings_back_and_forth(game):
            game.start_game()
            game.switch("s_plumb_bob", times=3)                      # all within 0.3 s
            expect(_player(game).tilt_warnings).to_equal(1)

        def it_starts_each_ball_with_no_warnings(game):
            game.start_game()
            game.switch("s_plumb_bob")
            game.drain()
            expect(_player(game).tilt_warnings).to_equal(0)

        def it_keeps_each_players_warnings_their_own(game):  # MPF: test_carry_over_multiple_player
            game.start_game(players=2)
            game.switch("s_plumb_bob")
            game.drain()
            expect(game.game.players[1].get("tilt_warnings", 0)).to_equal(0)

        def it_waits_for_the_bob_to_settle_before_the_next_ball(game):
            game.start_game()
            for _ in range(3):
                game.switch("s_plumb_bob")
                game.advance(1)                                      # third warning tilts at about 2 s
            game.drain()
            expect(game).not_to_have_posted("tilt_clear")            # 5 s from the last swing
            game.advance(5)
            expect(game).to_have_posted("tilt_clear", times=1)

    def describe_slam_tilt():  # MPF: test_slam_tilt
        def it_ends_the_game_after_this_ball(game):
            game.start_game()
            _player(game).extra_balls = 1
            game.switch("s_slam")
            expect(game).to_have_posted("slam_tilt", times=1)
            game.drain()
            expect(game.game).to_be_none()                           # no extra ball, no ball 2

        def it_does_nothing_but_post_between_games(game):
            game.switch("s_slam")
            expect(game).to_have_posted("slam_tilt", times=1)
            expect(game.game).to_be_none()

    def describe_the_look():
        def it_shows_a_warning_for_a_second_and_tilt_until_it_clears(tmp_path):
            rig = _rig(tmp_path, example="display")
            try:
                rig.start_game()
                rig.switch("s_plumb_bob")
                expect(rig.scene()).to_equal("tilt_warning")
                rig.advance(1)
                expect(rig.scene()).to_equal("score")
                rig.switch("s_plumb_bob")
                expect(rig.screen()).to_equal(["WARNING", "WARNING"])
                rig.switch("s_tilt")
                expect(rig.scene()).to_equal("tilted")
                rig.drain()
                rig.advance(5)
                expect(rig.scene()).not_to_equal("tilted")
            finally:
                rig.stop()


def describe_customizing_it():
    def it_takes_a_games_settings_and_look(tmp_path):  # Grand Prix's screens and callouts, Futurama's tag
        def edit(config):
            _with_tilt(config)
            config["switches"]["s_bob"] = {"number": "43", "tags": "tilt_bob"}

        folder = basic_machine(tmp_path, edit=edit, example="display", files={
            "assets/sounds/no.wav": "x",
            "modes/tilt/mode.py": """
                from vukery.media.scenes import Scene, Text, scene
                from vukery.modes import Moment, Tilt


                @scene
                def danger():
                    return Scene(Text("Danger"))


                class GrandPrixTilt(Tilt):
                    warnings_to_tilt = 2
                    tilt_warning_switch_tag = "tilt_bob"
                    look = Tilt.Look(warnings=(Moment(danger, 0.75, sound="no"),))
            """})
        rig = GameRig(folder)
        try:
            rig.start_game()
            rig.switch("s_plumb_bob")                    # tagged tilt_warning: not this game's bob
            expect(rig).not_to_have_posted("tilt_warning_1")
            rig.switch("s_bob")
            expect(rig.screen()).to_equal(["Danger"])
            expect(rig).to_have_played("no")
            rig.advance(1)
            rig.switch("s_bob")                          # the second warning tilts
            expect(rig).to_have_posted("tilt", times=1)
        finally:
            rig.stop()

    def it_refuses_to_change_how_it_works(tmp_path):
        with pytest.raises(ConfigError, match="can't change: tilt"):
            _rig(tmp_path, files={"modes/tilt/mode.py": """
                from vukery.modes import Tilt


                class Mine(Tilt):
                    def tilt(self, **_):
                        pass
            """})
