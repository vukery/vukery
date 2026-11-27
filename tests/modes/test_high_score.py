"""High score (an optional built-in mode, MPF's high_score): initials, the tables, and customizing it."""

import pytest
import yaml

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.modes.high_score import NO_NAME, Initials
from vukery.testing import GameRig, expect


def _with_high_score(config):
    config["modes"] = [*config["modes"], "high_score"]


def _rig(tmp_path, files=None):
    return GameRig(basic_machine(tmp_path, edit=_with_high_score, files=files, example="display"))


@pytest.fixture
def game(tmp_path):
    rig = _rig(tmp_path)
    yield rig
    rig.stop()


def _play(game, points_in_thousands, players=1):
    """Each player scores, then every ball drains: the game ends (and high score starts)."""
    game.start_game(players=players)
    for number in range(players):
        game.switch("s_target", times=points_in_thousands[number])
        game.drain()
    for _ in range(2 * players):   # balls 2 and 3
        game.drain()


def _enter(game, initials):
    """Pick each letter with the right flipper (it stays where the last one was taken), take it with start."""
    at = "A"
    for letter in initials:
        if steps := (ord(letter) - ord(at)) % 27:
            game.switch("s_right_flipper", times=steps)
        game.switch("s_start")
        at = letter


def describe_high_score():
    def it_only_runs_when_the_game_lists_it(tmp_path):
        rig = GameRig(basic_machine(tmp_path, example="display"))
        try:
            expect("high_score" in rig.machine.modes.modes).to_be_false()
        finally:
            rig.stop()

    def it_lets_the_game_end_when_nobody_beats_the_table(game):
        _play(game, [5])                                    # 5,000: below the lowest, 10,000
        expect(game.game).to_be_none()
        expect(game).not_to_have_posted("high_score_enter_initials")

    def it_holds_the_end_of_the_game_while_initials_are_entered(game):
        _play(game, [11])                                   # 11,000 beats LZZ's 10,000
        expect(game.game).not_to_be_none()
        expect(game.mode("high_score")).to_be_running()
        expect(game).to_have_posted("high_score_enter_initials", times=1)
        expect(game.screen()[:2]).to_equal(["PLAYER 1", "HIGH SCORE 4"])

    def it_takes_initials_with_the_flippers_and_start(game):
        _play(game, [11])
        game.switch("s_right_flipper", times=2)             # A → C
        game.switch("s_left_flipper")                       # back to B
        expect(game.display.values["high_score"]["letter"]).to_equal("B")
        game.switch("s_start")
        expect(game.display.values["high_score"]["initials"]).to_equal("B")

    def it_shows_the_award_then_lets_the_game_end(game):
        _play(game, [11])
        _enter(game, "ZOE")
        expect(game.screen()).to_equal(["ZOE", "HIGH SCORE 4", "11,000"])
        expect(game).to_have_posted("high_score_award_display", times=1)
        game.advance(4)
        expect(game).to_have_posted("high_score_complete", times=1)
        expect(game.game).to_be_none()

    def it_saves_the_tables_and_reads_them_back(game, tmp_path):
        _play(game, [45])                                   # between ERY (40,000) and VUK (50,000)
        _enter(game, "ZOE")
        game.advance(4)
        saved = yaml.safe_load((tmp_path / "machine" / "data" / "high_scores.yaml").read_text())
        expect([name for name, _ in saved["score"]]).to_equal(["VUK", "ZOE", "ERY", "PIN", "BAL"])
        again = GameRig(tmp_path / "machine")
        try:
            expect(again.display.values["high_score"]["score2_name"]).to_equal("ZOE")
        finally:
            again.stop()

    def it_gives_up_waiting_for_initials(game):
        _play(game, [11])
        game.advance(20)
        expect(game.display.values["high_score"]["name"]).to_equal(NO_NAME)

    def it_asks_each_player_in_turn(game):
        _play(game, [35, 25], players=2)                    # both make the five-entry table
        expect(game.display.values["high_score"]["player"]).to_equal(1)
        _enter(game, "AAA")
        expect(game.display.values["high_score"]["player"]).to_equal(2)

    def it_doesnt_count_a_tie_as_a_new_high_score(game):
        _play(game, [10])                                   # exactly LZZ's 10,000
        expect(game.game).to_be_none()

    def it_publishes_the_tables_for_scenes(game):
        values = game.display.values["high_score"]
        expect((values["score1_name"], values["score1_value"], values["score1_label"])).to_equal(
            ("VUK", 50_000, "GRAND CHAMPION"))


def describe_initials():
    def it_wraps_around_the_letters():
        initials = Initials()
        initials.left()
        expect(initials.letter).to_equal(" ")
        initials.right()
        initials.right()
        expect(initials.letter).to_equal("B")

    def it_takes_three_letters_then_stops():
        initials = Initials()
        for _ in range(5):
            initials.select()
        expect((initials.taken, initials.done)).to_equal(("AAA", True))

    def it_names_nobody_when_nothing_was_taken():
        expect(Initials().name()).to_equal(NO_NAME)


def describe_customizing_it():
    def it_takes_a_games_categories_labels_timing_and_look(tmp_path):
        rig = _rig(tmp_path, files={"modes/high_score/mode.py": """
            from vukery.media.scenes import Scene, Text, scene
            from vukery.modes import HighScore


            @scene
            def initials_please():
                return Scene(Text("MARINAIO {high_score.player}"))


            class CombatHighScore(HighScore):
                categories = {"score": ["AMMIRAGLIO", "PUNTEGGIO ELEVATO 1"]}
                defaults = {"score": [("ZAC", 3_000), ("CAR", 2_000)]}
                enter_initials_seconds = 45
                look = HighScore.Look(enter_initials=initials_please)
        """})
        try:
            _play(rig, [4])
            expect(rig.screen()).to_equal(["MARINAIO 1"])
            expect(rig.display.values["high_score"]["award"]).to_equal("AMMIRAGLIO")
        finally:
            rig.stop()

    def it_refuses_to_override_how_it_works(tmp_path):
        with pytest.raises(ConfigError, match="can't change: mode_start"):
            _rig(tmp_path, files={"modes/high_score/mode.py": """
                from vukery.modes import HighScore


                class Mine(HighScore):
                    def mode_start(self, **_):
                        pass
            """})

    def it_runs_a_games_own_high_score_instead(tmp_path):
        rig = _rig(tmp_path, files={"modes/high_score/mode.py": """
            from vukery import Mode


            class HighScore(Mode):   # not vukery's: replaces it
                game_mode = False
        """})
        try:
            expect(type(rig.mode("high_score")).__module__).to_contain("vukery_modes_")
        finally:
            rig.stop()

    def it_checks_the_tables_it_is_given(tmp_path):
        with pytest.raises(ConfigError, match="more entries than labels"):
            _rig(tmp_path, files={"modes/high_score/mode.py": """
                from vukery.modes import HighScore


                class Mine(HighScore):
                    categories = {"score": ["BEST"]}
                    defaults = {"score": [("A", 2), ("B", 1)]}
            """})
