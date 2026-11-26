"""Shows "press start" between games."""

from vukery import Mode

from .slides import SLIDES


class StartScreen(Mode):
    priority = 10
    start_on = ("reset_complete", "game_ended")  # at power-on, and after every game
    stop_on = "game_start"                        # gone as soon as a game starts
    game_mode = False         # runs outside games (a game mode only runs during one)
    stop_on_ball_end = False
    slides = SLIDES           # the slides this mode can show, by name (slides.py)

    def mode_start(self, **_):
        self.show_slide("start_screen")  # removed automatically when the mode stops
