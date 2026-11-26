"""Attract: runs between games and starts one when a start button is pressed.

Like MPF's attract mode, a switch tagged ``start`` asks to start a game. The
``request_to_start_game`` boolean event lets anything refuse (for example,
when not every ball is home), then ``game_start`` starts the game.
"""

from typing import Any

from vukery.core.modes import Mode, on


class Attract(Mode):
    priority = 10
    start_on = ("reset_complete", "game_ended")
    stop_on = "game_start"
    game_mode = False
    stop_on_ball_end = False

    @on.event("sw_start")
    def start_pressed(self, **_: Any) -> None:
        self.events.post_boolean("request_to_start_game", callback=self._may_start)

    def _may_start(self, ev_result: bool = True, **_: Any) -> None:
        if ev_result:
            self.events.post("game_start")
        else:
            self.info_log("A game can't start right now")
