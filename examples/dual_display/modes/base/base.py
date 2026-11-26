"""During a game: the score on the main display, player and ball on the apron."""

from vukery import Mode, on
from vukery.media.slides import Slide, Text


class Base(Mode):
    priority = 100
    start_on = "ball_started"

    slides = {
        "score": Slide(Text("{player.score:,}", y=0.5, size=0.3)),
        "ball_info": Slide(
            Text("PLAYER {player.number}", y=0.65, size=0.2),
            Text("BALL {player.ball}", y=0.3, size=0.2, color="ffcc00"),
            background="202060",
        ),
    }

    def mode_start(self, **_):
        self.show_slide("score", display="main")
        self.show_slide("ball_info", display="apron")

    @on.switch("s_target")
    def target(self):
        self.score(1000)

    @on.switch("s_left_sling")
    @on.switch("s_right_sling")
    def sling(self):
        self.score(10)
