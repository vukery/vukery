"""examples/display: what the display shows through a game."""

from pathlib import Path

import pytest

from vukery.testing import GameRig, expect

GAME = Path(__file__).parents[1]


@pytest.fixture
def game():
    # The test rig includes a media controller in the same process, so specs can
    # check what's on screen (game.slide(), game.screen()) without opening a window.
    rig = GameRig(GAME)
    yield rig
    rig.stop()


def describe_display():
    def describe_media_controller():
        def it_loads_one_for_its_display(game):  # displays: main in the config
            # vuk us starts one media controller per display in the config
            expect(game.machine.media_controllers()).to_equal(["main"])

    def describe_between_games():
        def it_shows_press_start(game):
            expect(game.slide()).to_equal("start_screen")
            expect(game.screen()).to_equal(["vukery", "PRESS START"])

    def describe_during_a_game():
        def it_shows_the_score_and_ball(game):
            game.start_game()
            expect(game.slide()).to_equal("score")
            expect(game.screen()).to_equal(["0", "PLAYER 1   BALL 1"])  # the text, as drawn

        def it_updates_the_score_as_it_changes(game):
            game.start_game()
            game.switch("s_target")
            game.switch("s_target")
            expect(game.screen()[0]).to_equal("2,000")

        def it_shows_the_next_ball(game):
            game.start_game()
            game.drain()
            expect(game.screen()[1]).to_equal("PLAYER 1   BALL 2")

        def it_follows_whose_turn_it_is(game):
            game.start_game(players=2)
            game.switch("s_target")
            game.drain()
            expect(game.screen()).to_equal(["0", "PLAYER 2   BALL 1"])

    def describe_after_the_game():
        def it_goes_back_to_press_start(game):
            game.start_game()
            game.drain()
            game.drain()
            game.drain()
            expect(game.slide()).to_equal("start_screen")
