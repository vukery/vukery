"""Tilt: warnings from the plumb bob, then a tilted ball, as MPF's ``tilt`` mode.

An optional built-in mode: list ``tilt`` in ``modes:``. It runs all the time,
even between games, so a slam tilt is always caught.

- A switch tagged ``tilt_warning`` (the plumb bob) gives the player a warning,
  unless it closes again within ``multiple_hit_window`` (one nudge can close
  it several times). The game posts ``tilt_warning_1``, ``tilt_warning_2``…
- The warning that reaches ``warnings_to_tilt``, or a switch tagged
  ``tilt``, tilts the ball: ``tilt`` is posted, the ball ends (its modes stop,
  the flippers and slingshots go dead), and ``ball_ending`` is held until
  every ball in play has drained and the bob has been still for
  ``settle_time``. Then ``tilt_clear`` is posted and the next ball starts.
- A switch tagged ``slam_tilt`` tilts too, and the game ends after that ball
  (no extra balls).
- Warnings go back to zero on ``reset_warnings_events`` (each ball's end).

A game customizes it with a subclass (``modes/tilt/mode.py``): the settings
below, with MPF's names (times in seconds), and its ``look``.
"""

from dataclasses import dataclass
from typing import Any, ClassVar

from vukery.media.scenes import Scene, SceneFunction, Text, scene
from vukery.modes.built_in import BuiltInMode


@scene
def tilt_warning() -> Scene:
    return Scene(Text("WARNING", size=0.25, color="ffcc00"))


@scene
def tilt_danger() -> Scene:
    return Scene(Text("WARNING", y=0.65, size=0.2, color="ff6600"), Text("WARNING", y=0.35, size=0.2, color="ff6600"))


@scene
def tilted() -> Scene:
    return Scene(Text("TILT", size=0.35, color="ff0000").blinks(every=0.5, fade=True))


@dataclass(frozen=True)
class Moment:
    """What the display (and speakers) do at a moment: a scene, for some seconds or until it's over, and a sound."""

    scene: SceneFunction | None = None
    seconds: float | None = None   # MPF: the slide's expire. None: until the tilt clears (or the next moment)
    sound: str | None = None


class Tilt(BuiltInMode, built_in=True):
    optional = True
    customizable = frozenset({"warnings_to_tilt", "multiple_hit_window", "settle_time", "reset_warnings_events",
                              "tilt_warning_switch_tag", "tilt_switch_tag", "slam_tilt_switch_tag",
                              "tilt_warnings_player_var", "look"})
    priority = 1_000_000               # as MPF's: its scenes cover everything
    start_on = "reset_complete"
    game_mode = False
    stop_on_ball_end = False

    @dataclass(frozen=True)
    class Look:
        warnings: tuple[Moment, ...] = (Moment(tilt_warning, 1.0), Moment(tilt_danger, 2.0))  # in turn; the last repeats
        tilt: Moment = Moment(tilted)

    warnings_to_tilt: ClassVar[int] = 3
    multiple_hit_window: ClassVar[float] = 0.3
    settle_time: ClassVar[float] = 5.0
    reset_warnings_events: ClassVar[tuple[str, ...]] = ("ball_will_end",)
    tilt_warning_switch_tag: ClassVar[str] = "tilt_warning"
    tilt_switch_tag: ClassVar[str] = "tilt"
    slam_tilt_switch_tag: ClassVar[str] = "slam_tilt"
    tilt_warnings_player_var: ClassVar[str] = "tilt_warnings"
    look: ClassVar[Look] = Look()

    def __init__(self, machine: Any):
        super().__init__(machine)
        self._handlers: list[Any] = []
        self._while_tilted: list[Any] = []
        self._last_warning: float | None = None       # when the last counted warning was
        self._last_bob: float | None = None           # when the bob last closed at all (for settling)
        self._balls_to_collect = 0
        self._ball_ending: Any = None                 # the held ball_ending queue
        self._showing: SceneFunction | None = None

    def scene_functions(self) -> tuple[SceneFunction, ...]:
        moments = (*self.look.warnings, self.look.tilt)
        return tuple(dict.fromkeys(m.scene for m in moments if m.scene is not None))

    # --- running all the time

    def mode_start(self, **_: Any) -> None:
        events = self.machine.events
        self._handlers = [
            events.add_handler(f"sw_{self.tilt_warning_switch_tag}", self._bob),
            events.add_handler(f"sw_{self.tilt_switch_tag}", self.tilt),
            events.add_handler(f"sw_{self.slam_tilt_switch_tag}", self.slam_tilt),
            *(events.add_handler(event, self.reset_warnings) for event in self.reset_warnings_events),
        ]

    def mode_stop(self, **_: Any) -> None:
        self.machine.events.remove_handlers([*self._handlers, *self._while_tilted])
        self._handlers, self._while_tilted = [], []

    def _playing(self) -> bool:
        game = self.machine.game
        return bool(game and game.player and not game.ending and not game.tilted)

    def _bob(self, **_: Any) -> None:
        now = self.machine.clock.now()
        self._last_bob = now
        if self._last_warning is None or now >= self._last_warning + self.multiple_hit_window:
            self.warning()

    def warning(self, **_: Any) -> None:
        """A tilt warning for the player: the one that reaches ``warnings_to_tilt`` tilts."""
        self._last_bob = self.machine.clock.now()
        if not self._playing():
            return
        assert self.machine.game is not None and self.machine.game.player is not None
        self._last_warning = self.machine.clock.now()
        player = self.machine.game.player
        warnings = int(player.get(self.tilt_warnings_player_var, 0) or 0) + 1
        setattr(player, self.tilt_warnings_player_var, warnings)
        if warnings >= self.warnings_to_tilt:
            self.tilt()
            return
        self.info_log("Tilt warning %s of %s", warnings, self.warnings_to_tilt)
        self.post("tilt_warning", warnings=warnings, warnings_remaining=self.warnings_to_tilt - warnings)
        self.post(f"tilt_warning_{warnings}")
        if self.look.warnings:
            self._show(self.look.warnings[min(warnings, len(self.look.warnings)) - 1])

    def reset_warnings(self, **_: Any) -> None:
        game = self.machine.game
        if game and game.player and not game.ending:
            setattr(game.player, self.tilt_warnings_player_var, 0)

    # --- tilting

    def tilt(self, **_: Any) -> None:
        """Tilt the ball: it ends, and the next one waits until the balls are in and the bob is still."""
        game = self.machine.game
        if not game or game.tilted or game.ending:
            return
        game.tilted = True
        self._balls_to_collect = game.balls_in_play
        self.info_log("Tilt. Balls to collect: %s", self._balls_to_collect)
        self.post("tilt")
        self._show(self.look.tilt)
        events = self.machine.events
        self._while_tilted = [events.add_handler("ball_ending", self._hold_ball_ending, priority=-1)]
        for device in self.machine.ball_devices.values():
            if "drain" in device.config.tags:
                self._while_tilted.append(events.add_handler(f"balldevice_{device.name}_ball_enter", self._drained))
        game.end_ball()

    def slam_tilt(self, **_: Any) -> None:
        self.post("slam_tilt")
        game = self.machine.game
        if not game:
            return
        game.slam_tilted = True
        self.tilt()

    def _drained(self, unclaimed_balls: int = 1, **_: Any) -> None:
        self._balls_to_collect -= unclaimed_balls
        if self._balls_to_collect <= 0:
            self._done()

    def _hold_ball_ending(self, queue: Any, **_: Any) -> None:
        self._ball_ending = queue
        queue.wait()
        if self._balls_to_collect <= 0:
            self._done()

    def _done(self) -> None:
        """Once the balls are in: wait for the bob to settle, then clear the tilt."""
        remaining = self._settle_remaining()
        if remaining > 0:
            self.delay("settle", remaining, self._done)
            return
        game = self.machine.game
        if game:
            game.tilted = False
        self.post("tilt_clear")
        self._hide()
        self.machine.events.remove_handlers(self._while_tilted)
        self._while_tilted = []
        if self._ball_ending is not None:
            queue, self._ball_ending = self._ball_ending, None
            queue.clear()

    def _settle_remaining(self) -> float:
        if self._last_bob is None:
            return 0.0
        return max(self._last_bob + self.settle_time - self.machine.clock.now(), 0.0)

    # --- the look

    def _show(self, moment: Moment) -> None:
        self._hide()
        if moment.sound:
            self.play_sound(moment.sound)
        if moment.scene is not None:
            self.show_scene(moment.scene)
            self._showing = moment.scene
            if moment.seconds is not None:
                self.delay("scene", moment.seconds, self._hide)

    def _hide(self) -> None:
        self.cancel_delay("scene")
        if self._showing is not None:
            self.remove_scene(self._showing)
            self._showing = None
