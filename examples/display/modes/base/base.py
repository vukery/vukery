"""The base mode: scores the playfield and shows the score."""

from vukery import Mode
from vukery.media.slides import Slide, Text


class Base(Mode):
    priority = 100
    start_on = "ball_started"

    slides = {
        "score": Slide(
            # {player.score:,} is filled in live by the media controller, with Python
            # formatting: 12340 shows as 12,340. Any player variable works.
            Text("{player.score:,}", y=0.55, size=0.25),
            Text("PLAYER {player.number}   BALL {player.ball}", y=0.15, size=0.07, color="aaaaaa"),
        ),
    }

    scoring = {                 # MPF: variable_player
        "s_target": 1000,
        "s_left_sling": 10,
        "s_right_sling": 10,
    }

    def mode_start(self, **_):
        # A slide's priority is the mode's (100 here), so it covers the start screen (10).
        self.show_slide("score")
