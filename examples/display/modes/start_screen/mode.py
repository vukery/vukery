"""Shows "press start" between games."""

from vukery import Mode

from .scenes import start_screen


class StartScreen(Mode):
    priority = 10
    start_on = ("reset_complete", "game_ended")  # at power-on, and after every game
    stop_on = "game_start"                        # gone as soon as a game starts
    game_mode = False         # runs outside games (a game mode only runs during one)
    stop_on_ball_end = False
    scenes = (start_screen,)  # the scenes this mode can show (scenes.py)

    def mode_start(self, **_):
        self.show_scene(start_screen)  # removed automatically when the mode stops
