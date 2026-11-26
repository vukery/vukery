"""examples/dual_display: two displays, each with its own slides."""

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


def describe_dual_display():
    def describe_media_controllers():
        def it_loads_one_per_display(game):  # displays: main and apron in the config
            # vuk it starts one media controller per display in the config
            expect(game.machine.media_controllers()).to_equal(["main", "apron"])

    def describe_between_games():
        def it_shows_the_title_on_main(game):
            expect(game.slide("main")).to_equal("title")
            expect(game.screen("main")).to_equal(["vukery"])

        def it_shows_press_start_on_the_apron(game):
            expect(game.slide("apron")).to_equal("press_start")  # pass a display name for the others
            expect(game.screen("apron")).to_equal(["PRESS START"])

    def describe_during_a_game():
        def it_shows_the_score_on_main(game):
            game.start_game()
            game.switch("s_target")
            expect(game.slide("main")).to_equal("score")
            expect(game.screen("main")).to_equal(["1,000"])

        def it_shows_player_and_ball_on_the_apron(game):
            game.start_game()
            expect(game.slide("apron")).to_equal("ball_info")
            expect(game.screen("apron")).to_equal(["PLAYER 1", "BALL 1"])

        def it_updates_each_display_on_its_own(game):
            game.start_game(players=2)
            game.switch("s_target")
            game.drain()
            expect(game.screen("main")).to_equal(["0"])
            expect(game.screen("apron")).to_equal(["PLAYER 2", "BALL 1"])

    def describe_after_the_game():
        def it_puts_both_displays_back(game):
            game.start_game()
            game.drain()
            game.drain()
            game.drain()
            expect(game.slide("main")).to_equal("title")
            expect(game.slide("apron")).to_equal("press_start")
