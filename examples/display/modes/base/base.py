"""The base mode: scores the playfield and shows the score."""

from vukery import Mode, on
from vukery.media.slides import Slide, Text


class Base(Mode):
    priority = 100
    start_on = "ball_started"

    slides = {
        "score": Slide(
            Text("{player.score:,}", y=0.55, size=0.25),
            Text("PLAYER {player.number}   BALL {player.ball}", y=0.15, size=0.07, color="aaaaaa"),
        ),
    }

    def mode_start(self, **_):
        self.show_slide("score")

    @on.switch("s_target")
    def target(self):
        self.score(1000)

    @on.switch("s_left_sling")
    @on.switch("s_right_sling")
    def sling(self):
        self.score(10)
