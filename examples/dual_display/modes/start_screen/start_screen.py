"""Between games: a title on the main display, "press start" on the apron."""

from vukery import Mode
from vukery.media.slides import Slide, Text


class StartScreen(Mode):
    priority = 10
    start_on = ("reset_complete", "game_ended")  # at power-on, and after every game
    stop_on = "game_start"
    game_mode = False         # runs outside games
    stop_on_ball_end = False

    slides = {
        "title": Slide(Text("vukery", y=0.5, size=0.25, color="ffcc00")),
        "press_start": Slide(Text("PRESS START", y=0.5, size=0.2), background="202060"),
    }

    def mode_start(self, **_):
        # display= picks the screen (MPF: slide_player target:). Each display keeps
        # its own stack of slides, so these don't compete.
        self.show_slide("title", display="main")
        self.show_slide("press_start", display="apron")
