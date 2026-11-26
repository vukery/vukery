"""During a game: the score on the main display, player and ball on the apron."""

from vukery import Mode

from .scoring import SCORING
from .slides import SLIDES


class Base(Mode):
    priority = 100
    start_on = "ball_started"
    scoring = SCORING
    slides = SLIDES

    def mode_start(self, **_):
        self.show_slide("score", display="main")        # covers the title (priority 100 > 10)
        self.show_slide("ball_info", display="apron")   # covers "PRESS START" on the apron
