"""examples/basic: the whole game flow, from attract to game over."""

from pathlib import Path

import pytest

from vukery.testing import GameRig, expect

GAME = Path(__file__).parents[1]


@pytest.fixture
def game():
    rig = GameRig(GAME)
    yield rig
    rig.stop()


def describe_basic():
    def describe_at_power_on():
        def it_runs_attract(game):
            expect(game.mode("attract")).to_be_running()
            expect(game.mode("base")).to_be_stopped()

    def describe_starting_a_game():
        def it_starts_the_first_ball(game):
            game.start_game()
            expect(game.mode("game")).to_be_running()
            expect(game.mode("attract")).to_be_stopped()
            expect(game.mode("base")).to_be_running()
            expect(game.player.ball).to_equal(1)
            expect(game).to_have_posted("ball_started", times=1)

        def it_ejects_a_ball_from_the_trough(game):
            game.start_game()
            expect(game.machine.trough().balls).to_equal(2)
            expect(game.game.balls_in_play).to_equal(1)

        def it_turns_on_the_flippers_and_slingshots(game):
            game.start_game()
            expect(len(game.machine.platform.rules)).to_equal(4)

        def it_refuses_to_start_unless_every_ball_is_home():
            rig = GameRig(GAME, fill_troughs=False)
            try:
                rig.switch("s_start")
                expect(rig.mode("attract")).to_be_running()
                expect(rig).not_to_have_posted("game_start")
            finally:
                rig.stop()

    def describe_scoring():
        def it_scores_1000_for_the_target(game):
            game.start_game()
            game.switch("s_target")
            expect(game.player.score).to_equal(1000)

        def it_scores_10_for_each_slingshot(game):
            game.start_game()
            game.switch("s_left_sling", "s_right_sling")
            game.switch("s_left_sling", times=3, every=0.1)
            expect(game.player.score).to_equal(50)

        def it_posts_score_changes(game):
            game.start_game()
            game.switch("s_target")
            expect(game).to_have_posted("player_score", times=1)

        def it_doesnt_score_in_attract(game):
            game.switch("s_target")
            expect(game.game).to_equal(None)

    def describe_draining():
        def it_starts_the_next_ball(game):
            game.start_game()
            game.drain()
            expect(game.player.ball).to_equal(2)
            expect(game).to_have_posted("ball_ended", times=1)

        def it_ends_the_game_after_three_balls(game):
            game.start_game()
            game.switch("s_target")
            game.drain()
            game.drain()
            game.drain()
            expect(game.game).to_equal(None)
            expect(game).to_have_posted("game_ended", times=1)
            expect(game.mode("attract")).to_be_running()
            expect(game.mode("base")).to_be_stopped()

        def it_turns_the_flippers_off_between_balls(game):
            game.start_game()
            game.switch("s_target")
            expect(game).to_have_posted("ball_will_end", times=0)
            game.drain()
            expect(game).to_have_posted("ball_will_end", times=1)

    def describe_two_players():
        def it_adds_a_player_when_start_is_pressed_again(game):
            game.start_game(players=2)
            expect(len(game.game.players)).to_equal(2)
            expect(game.player.number).to_equal(1)

        def it_alternates_turns(game):
            game.start_game(players=2)
            game.drain()
            expect(game.player.number).to_equal(2)
            expect(game.player.ball).to_equal(1)
            game.drain()
            expect(game.player.number).to_equal(1)
            expect(game.player.ball).to_equal(2)
