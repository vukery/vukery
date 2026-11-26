"""The base mode: scores the playfield and shows the score.

A mode is a folder: this file holds the class, and the files next to it hold
its parts (scoring.py, slides.py). A small mode can also be one file, as in
examples/basic.
"""

from vukery import Mode

from .scoring import SCORING  # files next to this one, in the same mode folder
from .slides import SLIDES


class Base(Mode):
    priority = 100
    start_on = "ball_started"
    scoring = SCORING           # MPF: variable_player
    slides = SLIDES

    def mode_start(self, **_):
        # A slide's priority is the mode's (100 here), so it covers the start screen (10).
        self.show_slide("score")
