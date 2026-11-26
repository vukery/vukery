"""Between games: a title on the main display, "press start" on the apron."""

from vukery import Mode

from .scenes import press_start, title


class StartScreen(Mode):
    priority = 10
    start_on = ("reset_complete", "game_ended")  # at power-on, and after every game
    stop_on = "game_start"
    game_mode = False         # runs outside games
    stop_on_ball_end = False
    scenes = (title, press_start)

    def mode_start(self, **_):
        # display= picks the screen (MPF: slide_player target:). Each display keeps
        # its own stack of scenes, so these don't compete.
        self.show_scene(title, display="main")
        self.show_scene(press_start, display="apron")
