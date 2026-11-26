"""Shows "press start" between games."""

from vukery import Mode
from vukery.media.slides import Slide, Text


class StartScreen(Mode):
    priority = 10
    start_on = ("reset_complete", "game_ended")
    stop_on = "game_start"
    game_mode = False
    stop_on_ball_end = False

    slides = {
        "start_screen": Slide(
            Text("vukery", y=0.6, size=0.2, color="ffcc00"),
            Text("PRESS START", y=0.3, size=0.08),
        ),
    }

    def mode_start(self, **_):
        self.show_slide("start_screen")
