"""The media controller's mixer: which sounds are playing, and how loud, from moment to moment.

Pure logic on a clock, so it's specced without a sound card. The audio
output (``vukery.mc.audio``) feeds it the engine's sound messages and each
sound's length, then plays what it says. It follows MPF's sound system:

- **Tracks** play up to ``simultaneous_sounds`` at once. When a track is
  full, a new sound with a higher priority stops the lowest-priority one
  playing (the oldest of those); otherwise it waits in the track's queue for
  up to its ``max_queue_time`` (``None``: as long as it takes; ``0``: it's
  dropped).
- **Loops:** ``0`` plays once, ``-1`` forever, ``2`` three times.
  ``start_at`` skips into the file the first time through. A ``stop_looping``
  lets the current pass finish.
- **Ducking:** while a sound plays, its ``ducking`` target track is turned
  down to ``attenuation`` over ``attack`` seconds, and back up over
  ``release`` seconds, starting ``release_point`` seconds before the sound
  ends (or when it's stopped).
- **Volume:** the sound's, times its track's, times any ducking on that track.
- **Joining late:** a play message with ``elapsed`` (from the welcome of a
  media controller that connected after the sound started) starts it that
  far in; one that's already over doesn't play.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Playing:
    """A sound that's playing (or waiting in its track's queue)."""

    id: int
    sound: str
    track: str
    volume: float
    priority: int
    loops: int
    start_at: float
    length: float | None          # seconds, if known
    ducking: dict[str, Any] | None
    max_queue_time: float | None
    queued_at: float
    started_at: float | None = None
    ends_at: float = math.inf     # when it stops by itself
    order: int = 0
    elapsed: float = 0.0          # how long ago it started, when we joined late

    @property
    def first_pass(self) -> float:
        return max((self.length or math.inf) - self.start_at, 0.0)


@dataclass
class _Duck:
    target: str
    attenuation: float
    attack: float
    started_at: float
    release: float
    release_at: float   # when it starts turning the target back up

    def factor(self, now: float) -> float:
        down = 1 - self.attenuation
        if now < self.release_at:
            reached = 1.0 if self.attack <= 0 else min((now - self.started_at) / self.attack, 1.0)
            return 1 - down * reached
        back = 1.0 if self.release <= 0 else min((now - self.release_at) / self.release, 1.0)
        return self.attenuation + down * back

    def done(self, now: float) -> bool:
        return now >= self.release_at + self.release


@dataclass
class Mixer:
    tracks: dict[str, dict[str, Any]]
    now: Callable[[], float]
    length: Callable[[str], float | None] = lambda _sound: None   # a sound's length in seconds, if known
    playing: list[Playing] = field(default_factory=list[Playing])
    queued: list[Playing] = field(default_factory=list[Playing])
    _ducks: dict[int, _Duck] = field(default_factory=dict[int, _Duck])
    _order: int = 0

    # --- messages from the engine

    def handle(self, message: dict[str, Any]) -> None:
        match message:
            case {"action": "play"}:
                self.play(message)
            case {"action": "stop", "id": int() as sound_id}:
                self.stop(sound_id)
            case {"action": "stop_looping", "id": int() as sound_id}:
                self.stop_looping(sound_id)
            case _:
                pass

    def play(self, message: dict[str, Any]) -> None:
        now = self.now()
        self._order += 1
        sound = Playing(int(message["id"]), str(message["sound"]), str(message["track"]), float(message["volume"]),
                        int(message.get("priority", 0)), int(message.get("loops", 0)),
                        float(message.get("start_at", 0.0)), self.length(str(message["sound"])),
                        message.get("ducking"), message.get("max_queue_time"), now, order=self._order,
                        elapsed=float(message.get("elapsed", 0.0)))
        self.update()
        on_track = [p for p in self.playing if p.track == sound.track]
        if len(on_track) < self._limit(sound.track):
            self._start(sound, now)
            return
        lowest = min(on_track, key=lambda p: (p.priority, p.order))
        if sound.priority > lowest.priority:
            self._end(lowest, now)
            self._start(sound, now)
        elif sound.max_queue_time is None or float(sound.max_queue_time) > 0:
            self.queued.append(sound)

    def stop(self, sound_id: int) -> None:
        now = self.now()
        self.queued = [q for q in self.queued if q.id != sound_id]
        for sound in [p for p in self.playing if p.id == sound_id]:
            self._end(sound, now)
        self.update()

    def stop_looping(self, sound_id: int) -> None:
        """Finish the pass it's on, then stop."""
        now = self.now()
        self.queued = [q for q in self.queued if q.id != sound_id]
        for sound in self.playing:
            if sound.id == sound_id and sound.started_at is not None and sound.length:
                elapsed = now - sound.started_at
                end = sound.started_at + sound.first_pass
                if elapsed > sound.first_pass:
                    end += math.ceil((elapsed - sound.first_pass) / sound.length) * sound.length
                sound.loops = 0
                sound.ends_at = min(sound.ends_at, end)
                if sound.id in self._ducks and sound.ducking:
                    self._ducks[sound.id].release_at = min(self._ducks[sound.id].release_at,
                                                           end - float(sound.ducking.get("release_point", 0)))

    # --- reading

    def position(self, sound: Playing) -> float:
        """Seconds into the file a playing sound is now (where to start a player that joins late)."""
        if sound.started_at is None:
            return 0.0
        elapsed = self.now() - sound.started_at
        if elapsed < sound.first_pass or not sound.length:
            return sound.start_at + elapsed
        return (elapsed - sound.first_pass) % sound.length

    def update(self) -> None:
        """Let sounds that are done end, drop queued sounds that waited too long, and start the next ones."""
        now = self.now()
        for sound in [p for p in self.playing if now >= p.ends_at]:
            self._end(sound, now)
        self.queued = [q for q in self.queued
                       if q.max_queue_time is None or now - q.queued_at <= float(q.max_queue_time)]
        for track in {q.track for q in self.queued}:
            while len([p for p in self.playing if p.track == track]) < self._limit(track):
                waiting = [q for q in self.queued if q.track == track]
                if not waiting:
                    break
                best = max(waiting, key=lambda q: (q.priority, -q.order))
                self.queued.remove(best)
                self._start(best, now)
        for sound_id in [i for i, duck in self._ducks.items() if duck.done(now)]:
            del self._ducks[sound_id]

    def volume(self, sound: Playing) -> float:
        """How loud a playing sound is right now: its volume, its track's, and any ducking."""
        now = self.now()
        track = float(self.tracks.get(sound.track, {}).get("volume", 0.5))
        ducked = 1.0
        for duck in self._ducks.values():
            if duck.target == sound.track:
                ducked *= duck.factor(now)
        return sound.volume * track * ducked

    # --- inside

    def _limit(self, track: str) -> int:
        return int(self.tracks.get(track, {}).get("simultaneous_sounds", 8))

    def _start(self, sound: Playing, now: float) -> None:
        sound.started_at = started = now - sound.elapsed
        if sound.length is not None and sound.loops >= 0:
            sound.ends_at = started + sound.first_pass + sound.loops * sound.length
        self.playing.append(sound)
        if sound.ducking:
            duck = sound.ducking
            release_at = sound.ends_at - float(duck.get("release_point", 0))
            self._ducks[sound.id] = _Duck(str(duck["target"]), float(duck.get("attenuation", 1.0)),
                                          float(duck.get("attack", 0.01)), started, float(duck.get("release", 0.01)),
                                          release_at)

    def _end(self, sound: Playing, now: float) -> None:
        if sound in self.playing:
            self.playing.remove(sound)
        if sound.id in self._ducks:   # turn the target back up from here, if it isn't already
            self._ducks[sound.id].release_at = min(self._ducks[sound.id].release_at, now)
