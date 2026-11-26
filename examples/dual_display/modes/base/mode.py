"""During a game: the score on the main display, player and ball on the apron."""

from vukery import Mode

from .scenes import ball_info, score


class Base(Mode):
    priority = 100
    start_on = "ball_started"
    scoring = {                 # what this mode scores (MPF: variable_player)
        "s_target": 1000,
        "s_left_sling": 10,
        "s_right_sling": 10,
    }
    scenes = (score, ball_info)

    def mode_start(self, **_):
        self.show_scene(score, display="main")        # covers the title (priority 100 > 10)
        self.show_scene(ball_info, display="apron")   # covers "PRESS START" on the apron
