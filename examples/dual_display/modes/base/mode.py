"""During a game: the score on the main display, player and ball on the apron."""

from vukery import Mode
from vukery.media.slides import Slide, Text


class Base(Mode):
    priority = 100
    start_on = "ball_started"

    slides = {
        "score": Slide(Text("{player.score:,}", y=0.5, size=0.3)),
        "ball_info": Slide(
            Text("PLAYER {player.number}", y=0.65, size=0.2),
            Text("BALL {player.ball}", y=0.3, size=0.2, color="ffcc00"),
            background="202060",   # six hex digits, like every color in vukery
        ),
    }

    scoring = {
        "s_target": 1000,
        "s_left_sling": 10,
        "s_right_sling": 10,
    }

    def mode_start(self, **_):
        self.show_slide("score", display="main")        # covers the title (priority 100 > 10)
        self.show_slide("ball_info", display="apron")   # covers "PRESS START" on the apron
