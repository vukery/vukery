"""The base mode: just enough for the reference config to run a game.

examples/reference is about the config; the game side (scoring, scenes,
shows) is taught by examples/basic and examples/display.
"""

from vukery import Mode


class Base(Mode):
    priority = 100
    start_on = "ball_started"
    scoring = {
        "s_target": 1000,
    }
