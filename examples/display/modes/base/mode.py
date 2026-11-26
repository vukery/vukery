"""The base mode: scores the playfield and shows the score.

A mode is a folder: this file holds the class and what configures it (its
settings, its scoring table), and the files next to it hold its bigger parts
(scenes.py). A small mode can also be one file, as in examples/basic.
"""

from vukery import Mode, on

from .scenes import score  # a file next to this one, in the same mode folder


class Base(Mode):
    priority = 100
    start_on = "ball_started"
    scoring = {                 # what this mode scores (MPF: variable_player)
        "s_target": 1000,
        "s_left_sling": 10,
        "s_right_sling": 10,
    }
    scenes = (score,)           # the scenes it can show (scenes.py)

    def mode_start(self, **_):
        # A scene's priority is the mode's (100 here), so it covers the start screen (10).
        self.show_scene(score)

    @on.switch("s_target")
    def target_hit(self):
        # Every file in assets/sounds/ is a sound, named by its file name: target_hit.wav
        # is "target_hit" (MPF: sound_player). The media controller mixes and plays it.
        self.play_sound("target_hit")
