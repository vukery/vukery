"""Frenzy: lit by every third target, for 10 seconds.

Shows priority and scoring blocks. Frenzy (priority 200) runs above Base (100):
- the target scores 5000 *instead of* Base's 1000 (block=True);
- slingshots score 100 *as well as* Base's 10 (no block): 110.

Its light (l_frenzy) is on while it runs.
"""

from vukery import Mode, Score

FRENZY_SECONDS = 10


class Frenzy(Mode):
    priority = 200              # above Base (100), so Frenzy's scoring runs first and can block Base's
    start_on = "frenzy_lit"     # Base posts this on every third target

    scoring = {
        # block=True: lower-priority modes don't score this hit (MPF's |block).
        # Only their scoring is blocked; Base's other handlers for the target still run.
        "s_target": Score(5000, block=True),
        # No block: Base's 10 is added too, for 110.
        "s_left_sling": 100,
        "s_right_sling": 100,
    }

    def mode_start(self, **_):  # called once the mode has started
        # Stop after 10 seconds. Delays are cancelled automatically if the mode stops
        # first (e.g. the ball drains, since stop_on_ball_end is True by default).
        self.delay("over", FRENZY_SECONDS, self.stop)
        self.machine.lights["l_frenzy"].on()  # lights come from config: lights:

    def mode_stop(self, **_):   # called as the mode stops, for any reason
        self.machine.lights["l_frenzy"].off()
