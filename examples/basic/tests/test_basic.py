"""examples/basic: the whole game flow, from attract to game over.

Specs are RSpec-style: describe_ blocks group them, it_ functions are the
specs. Run them with `uv run pytest`.
"""

from pathlib import Path

import pytest

from vukery.testing import GameRig, expect

GAME = Path(__file__).parents[1]  # the game folder (the one with config/ and modes/)


@pytest.fixture
def game():
    # GameRig runs the game in the test environment on virtual time:
    # nothing happens until a spec does something, and time only moves with advance().
    rig = GameRig(GAME)
    yield rig
    rig.stop()


def describe_basic():
    def describe_at_power_on():
        def it_loads_no_media_controller(game):  # no displays: in the config
            expect(game.machine.media).to_equal(None)
            expect(game.machine.media_controllers()).to_equal([])

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
            game.start_game()  # presses the start button (the switch tagged start)
            expect(game.machine.trough().balls).to_equal(2)
            expect(game.game.balls_in_play).to_equal(1)

        def it_turns_on_the_flippers_and_slingshots(game):
            game.start_game()
            expect(len(game.machine.platform.rules)).to_equal(4)

        def it_refuses_to_start_unless_every_ball_is_home():
            rig = GameRig(GAME, fill_troughs=False)  # an empty trough: balls aren't home
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
            game.switch("s_left_sling", "s_right_sling")       # both at the same moment
            game.switch("s_left_sling", times=3, every=0.1)    # three hits, 0.1 seconds apart
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
            game.drain()  # returns the ball to the trough, which ends the ball
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

    def describe_frenzy():  # priority and scoring blocks
        def _light_frenzy(game):  # helpers start with _ so pytest-describe doesn't run them as specs
            game.switch("s_target", times=3)  # 3000 points, and Frenzy lights

        def it_starts_after_three_targets(game):
            game.start_game()
            game.switch("s_target", times=2)
            expect(game.mode("frenzy")).to_be_stopped()
            game.switch("s_target")
            expect(game.mode("frenzy")).to_be_running()

        def it_replaces_the_targets_points_instead_of_adding(game):
            game.start_game()
            _light_frenzy(game)
            game.switch("s_target")
            expect(game.player.score).to_equal(3000 + 5000)  # not + 6000: Base's 1000 is blocked

        def it_adds_to_the_slingshots_points(game):
            game.start_game()
            _light_frenzy(game)
            game.switch("s_left_sling")
            expect(game.player.score).to_equal(3000 + 110)  # Frenzy's 100 and Base's 10

        def it_still_runs_base_handlers_that_arent_scoring(game):
            game.start_game()
            _light_frenzy(game)
            game.switch("s_target", times=2)
            expect(game.player.targets).to_equal(5)  # Base kept counting under the block

        def it_lights_its_light_while_it_runs(game):
            game.start_game()
            _light_frenzy(game)
            expect(game.machine.lights["l_frenzy"].current_color()).to_equal((255, 255, 255))
            game.advance(10)  # Frenzy ends
            expect(game.machine.lights["l_frenzy"].current_color()).to_equal((0, 0, 0))

        def it_ends_after_ten_seconds(game):
            game.start_game()
            _light_frenzy(game)
            game.advance(10)  # virtual time: 10 seconds pass instantly
            expect(game.mode("frenzy")).to_be_stopped()
            game.switch("s_target")
            expect(game.player.score).to_equal(3000 + 1000)  # back to Base's points

        def it_ends_with_the_ball(game):
            game.start_game()
            _light_frenzy(game)
            game.drain()
            expect(game.mode("frenzy")).to_be_stopped()

        def it_doesnt_restart_while_running(game):
            game.start_game()
            _light_frenzy(game)
            game.switch("s_target", times=3)
            expect(game).to_have_posted("frenzy_lit", times=1)

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
