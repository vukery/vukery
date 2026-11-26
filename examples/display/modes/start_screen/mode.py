"""Shows "press start" between games."""

from vukery import Mode
from vukery.media.slides import Slide, Text


class StartScreen(Mode):
    priority = 10
    start_on = ("reset_complete", "game_ended")  # at power-on, and after every game
    stop_on = "game_start"                        # gone as soon as a game starts
    game_mode = False         # runs outside games (a game mode only runs during one)
    stop_on_ball_end = False

    # The slides this mode can show, by name. The engine sends these to the media
    # controller as data; positions and sizes are fractions of the display.
    slides = {
        "start_screen": Slide(
            Text("vukery", y=0.6, size=0.2, color="ffcc00"),
            Text("PRESS START", y=0.3, size=0.08),
        ),
    }

    def mode_start(self, **_):
        self.show_slide("start_screen")  # removed automatically when the mode stops
