"""The base mode: runs for every ball and scores the playfield."""

from vukery import Mode, on


class Base(Mode):
    priority = 100
    start_on = "ball_started"

    @on.switch("s_target")
    def target(self):
        self.score(1000)

    @on.switch("s_left_sling")
    @on.switch("s_right_sling")
    def sling(self):
        self.score(10)
