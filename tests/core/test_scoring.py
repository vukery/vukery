"""Scoring tables, blocking and score adjusters, on a small game built for these specs."""

import textwrap
from pathlib import Path

import pytest
import yaml

from vukery.testing import GameRig, expect

BASIC = Path(__file__).parents[2] / "examples" / "basic" / "config" / "machine.yaml"

MODES = {
    "base": '''
        from vukery import Award, Mode, on


        class Base(Mode):
            priority = 100
            start_on = "ball_started"

            scoring = {
                "s_target": 1000,
                "sw_pops": 100,
                "s_lane": Award(lanes=1),
                "s_spinner": lambda mode: 10 * (mode.player.get("lanes", 0) + 1),
                "s_hole": 500,
                "ramp_made": 2500,
            }

            @on.switch("s_pop")
            def pop_sound(self):
                self.player.pop_sounds = self.player.get("pop_sounds", 0) + 1
    ''',
    "super_pops": '''
        from vukery import Mode, Score


        class SuperPops(Mode):
            priority = 200
            start_on = "super_pops_lit"

            scoring = {
                "sw_pops": Score(1000, block=True),
            }
    ''',
    "hole_lit": '''
        from vukery import Mode, Score


        class HoleLit(Mode):
            priority = 200
            start_on = "ball_started"

            scoring = {
                "s_hole": Score(5000, block=lambda mode: mode.player.get("hole_lit", False)),
            }
    ''',
    "multiplier": '''
        from vukery import Mode


        class Multiplier(Mode):
            priority = 300
            start_on = "ball_started"

            def adjust_score(self, points, source):
                return points * self.player.get("multiplier", 1)
    ''',
    "red_line": '''
        from vukery import Mode


        class RedLine(Mode):
            priority = 400
            start_on = "red_line_reached"

            def adjust_score(self, points, source):
                return 0 if source != "s_target" else points
    ''',
}


@pytest.fixture
def game(tmp_path):
    config = yaml.safe_load(BASIC.read_text())
    config["switches"].update({
        "s_pop": {"number": "20", "tags": "pops"},
        "s_lane": {"number": "21"},
        "s_spinner": {"number": "22"},
        "s_hole": {"number": "23"},
    })
    config["modes"] = list(MODES)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "machine.yaml").write_text(yaml.safe_dump(config))
    for name, code in MODES.items():
        (tmp_path / "modes" / name).mkdir(parents=True)
        (tmp_path / "modes" / name / "mode.py").write_text(textwrap.dedent(code))
    rig = GameRig(tmp_path)
    rig.start_game()
    yield rig
    rig.stop()


def describe_scoring_tables():
    def it_scores_a_switch(game):
        game.switch("s_target")
        expect(game.player.score).to_equal(1000)

    def it_scores_a_switch_tag(game):
        game.switch("s_pop")
        expect(game.player.score).to_equal(100)

    def it_scores_an_event(game):
        game.post("ramp_made")
        expect(game.player.score).to_equal(2500)

    def it_computes_points_with_a_function(game):
        game.switch("s_lane", times=2)
        game.switch("s_spinner")
        expect(game.player.score).to_equal(30)  # 10 x (2 lanes + 1)

    def it_awards_other_player_variables(game):
        game.switch("s_lane", times=3)
        expect(game.player.lanes).to_equal(3)
        expect(game.player.score).to_equal(0)

    def it_doesnt_score_once_the_mode_stops(game):
        game.drain()
        game.drain()
        game.drain()
        game.switch("s_target")
        expect(game.game).to_equal(None)


def describe_blocking():
    def it_lets_a_higher_mode_replace_a_lower_ones_points(game):
        game.post("super_pops_lit")
        game.switch("s_pop")
        expect(game.player.score).to_equal(1000)  # not 1100

    def it_still_runs_the_lower_modes_other_handlers(game):
        game.post("super_pops_lit")
        game.switch("s_pop")
        expect(game.player.pop_sounds).to_equal(1)

    def it_only_blocks_while_its_mode_runs(game):
        game.switch("s_pop")
        expect(game.player.score).to_equal(100)

    def describe_a_conditional_block():
        def it_blocks_when_the_condition_holds(game):
            game.player.hole_lit = True
            game.switch("s_hole")
            expect(game.player.score).to_equal(5000)

        def it_adds_up_when_it_doesnt(game):
            game.switch("s_hole")
            expect(game.player.score).to_equal(5500)


def describe_adjusters():
    def it_multiplies_every_score(game):
        game.player.multiplier = 3
        game.switch("s_target")
        game.switch("s_pop")
        expect(game.player.score).to_equal(3300)

    def it_doesnt_multiply_awards(game):
        game.player.multiplier = 3
        game.switch("s_lane")
        expect(game.player.lanes).to_equal(1)

    def it_lets_a_mode_suppress_scoring(game):
        game.post("red_line_reached")
        game.switch("s_pop")
        game.switch("s_target")
        expect(game.player.score).to_equal(1000)  # only the target still scores

    def it_applies_adjusters_highest_priority_first(game):
        game.post("red_line_reached")  # priority 400: zero unless it's the target
        game.player.multiplier = 2      # priority 300: then double
        game.switch("s_target")
        expect(game.player.score).to_equal(2000)


def describe_scoring_values():
    def it_needs_a_variable_for_an_award():
        from vukery import Award

        with pytest.raises(ValueError, match="at least one variable"):
            Award()

    def it_keeps_the_score_to_score_values():
        from vukery import Award

        with pytest.raises(ValueError, match="Use Score"):
            Award(score=100)

    def it_describes_an_award():
        from vukery import Award

        expect(repr(Award(lanes=1))).to_equal("Award(lanes=1, block=False)")

    @pytest.mark.parametrize("value", [True, "1000", 2.5])
    def it_refuses_things_that_arent_points(value):
        from vukery.core.scoring import entries

        with pytest.raises(TypeError, match="Not a scoring value"):
            entries(value)
