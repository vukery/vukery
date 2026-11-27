"""use_wait_queue (MPF's): a mode started by a queue event holds it until the mode stops."""

from tests.helpers import basic_machine
from vukery.testing import GameRig, expect

GAME_OVER = """
    from vukery import Mode, on


    class GameOver(Mode):
        start_on = "game_ending"
        use_wait_queue = True       # the game ends when this mode stops
        game_mode = False
        stop_on_ball_end = False

        def mode_start(self, **_):
            self.delay("over", 5, self.stop)

        @on.event("sw_start")
        def skip(self, **_):
            self.stop()
"""


def _game(tmp_path):
    def edit(config):
        config["modes"] = [*config["modes"], "game_over"]

    return GameRig(basic_machine(tmp_path, edit=edit, files={"modes/game_over/mode.py": GAME_OVER}))


def describe_use_wait_queue():
    def it_holds_the_queue_event_until_the_mode_stops(tmp_path):
        game = _game(tmp_path)
        try:
            game.start_game()
            for _ in range(3):   # three balls
                game.drain()
            game.advance(1)
            expect(game.mode("game_over")).to_be_running()
            expect(game.game).not_to_be_none()           # still ending
            game.advance(5)
            expect(game.game).to_be_none()
            expect(game).to_have_posted("game_ended", times=1)
        finally:
            game.stop()

    def it_lets_go_as_soon_as_the_mode_stops_early(tmp_path):
        game = _game(tmp_path)
        try:
            game.start_game()
            for _ in range(3):   # three balls
                game.drain()
            game.switch("s_start")
            expect(game.game).to_be_none()
        finally:
            game.stop()
