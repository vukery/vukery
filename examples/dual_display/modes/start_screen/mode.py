"""Between games: a title on the main display, "press start" on the apron."""

from vukery import Mode

from .slides import SLIDES


class StartScreen(Mode):
    priority = 10
    start_on = ("reset_complete", "game_ended")  # at power-on, and after every game
    stop_on = "game_start"
    game_mode = False         # runs outside games
    stop_on_ball_end = False
    slides = SLIDES

    def mode_start(self, **_):
        # display= picks the screen (MPF: slide_player target:). Each display keeps
        # its own stack of slides, so these don't compete.
        self.show_slide("title", display="main")
        self.show_slide("press_start", display="apron")
