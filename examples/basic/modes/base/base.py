"""The base mode: runs for every ball, scores the playfield, and lights Frenzy."""

from vukery import Mode, on

TARGETS_FOR_FRENZY = 3


class Base(Mode):
    priority = 100              # higher priorities handle switches first (and can block lower ones)
    start_on = "ball_started"   # starts with every ball; a game mode also stops when the ball ends

    # What this mode scores. Keys are switch names (or switch tags / event names),
    # values are points. MPF: variable_player: s_target_active: score: 1000
    scoring = {
        "s_target": 1000,
        "s_left_sling": 10,
        "s_right_sling": 10,
    }

    @on.switch("s_target")      # runs whenever the target is hit, alongside the scoring table
    def count_target(self):
        # Player variables are plain attributes, kept per player across balls.
        self.player.targets = self.player.get("targets", 0) + 1
        # An ordinary handler, not scoring: Frenzy's scoring block doesn't stop it.
        if self.player.targets % TARGETS_FOR_FRENZY == 0 and not self.machine.modes["frenzy"].active:
            self.post("frenzy_lit")  # any mode can start on this event (Frenzy does)
