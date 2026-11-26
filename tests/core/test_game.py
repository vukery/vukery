"""The game loop: players, extra balls, and modes that only run in a game."""

import pytest

from tests.helpers import basic_machine
from vukery.testing import GameRig, expect


@pytest.fixture
def game(tmp_path):
    def edit(config):
        config["player_vars"] = {"lanes": {"initial_value": 2}, "bonus_x": {}, "nickname": "ACE"}

    rig = GameRig(basic_machine(tmp_path, edit=edit))
    yield rig
    rig.stop()


def describe_the_game():
    def describe_player_variables():
        def it_starts_each_player_with_the_configured_values(game):  # MPF: player_vars: initial_value:
            game.start_game()
            expect((game.player.lanes, game.player.bonus_x, game.player.nickname)).to_equal((2, 0, "ACE"))

    def describe_extra_balls():
        def it_plays_an_extra_ball_before_the_next_ball(game):
            game.start_game()
            game.player.extra_balls = 1
            game.drain()
            expect(game.player.ball).to_equal(1)            # the same ball again
            expect(game).to_have_posted("ball_started", times=2)
            game.drain()
            expect(game.player.ball).to_equal(2)

        def it_tells_modes_which_ball_is_an_extra_ball(game):
            game.start_game()
            game.player.extra_balls = 1
            game.drain()
            started = [kwargs for event, kwargs in game.posted if event == "ball_started"]
            expect([s["is_extra_ball"] for s in started]).to_equal([False, True])

    def describe_game_modes():
        def it_doesnt_start_a_game_mode_without_a_game(game):
            game.mode("frenzy").start()
            game.advance()
            expect(game.mode("frenzy")).to_be_stopped()

        def it_ignores_a_second_start_and_stop(game):
            game.start_game()
            game.mode("frenzy").start()
            game.mode("frenzy").start()
            game.advance()
            expect(game.times_posted("mode_frenzy_started")).to_equal(1)
            game.mode("frenzy").stop()
            game.mode("frenzy").stop()
            game.advance()
            expect(game.times_posted("mode_frenzy_stopped")).to_equal(1)
