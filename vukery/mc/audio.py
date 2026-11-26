"""Sound output: plays what the mixer says, with pyglet (and FFmpeg for .ogg and friends).

Each frame, ``Audio.frame()`` hands the engine's sound messages to the
``Mixer``, then starts, stops and sets the volume of a pyglet player per
playing sound. If the machine has no working sound output, it logs that once
and stays quiet: the displays keep going.
"""

from pathlib import Path
from typing import Any

from vukery.core.log import get_logger
from vukery.mc.mixer import Mixer
from vukery.mc.state import MediaState

log = get_logger("mc.audio")
STREAM_BYTES = 1_000_000   # files bigger than this (music) stream from disk; smaller ones are decoded once


class Audio:
    def __init__(self, state: MediaState) -> None:
        self.state = state
        self.mixer: Mixer | None = None
        self.players: dict[int, Any] = {}
        self._static: dict[str, Any] = {}
        self._lengths: dict[str, float | None] = {}
        self._tracks: Any = None
        self.broken = False

    def frame(self) -> None:
        """Catch up with the engine's messages and the clock."""
        if self.broken or not self.state.connected:
            return
        if self.state.tracks is not self._tracks:   # a (new) welcome: start over
            self._stop_all()
            self._tracks = self.state.tracks
            self.mixer = Mixer(self.state.tracks, self.state.now, self._length)
            self._preload()
        assert self.mixer is not None
        try:
            while self.state.sound_messages:
                self.mixer.handle(self.state.sound_messages.popleft())
            self.mixer.update()
            playing = {sound.id: sound for sound in self.mixer.playing}
            for sound_id in [i for i in self.players if i not in playing]:
                self.players.pop(sound_id).delete()
            for sound_id, sound in playing.items():
                player = self.players.get(sound_id) or self._start(sound)
                player.volume = self.mixer.volume(sound)
        except Exception:
            log.exception("Sound output failed; carrying on without sound")
            self.broken = True
            self._stop_all()

    def _start(self, sound: Any) -> Any:
        import pyglet

        player = pyglet.media.Player()
        player.queue(self._source(sound.sound))
        player.loop = sound.loops != 0      # the mixer decides when a looping sound has played enough
        if sound.start_at:
            player.seek(sound.start_at)
        player.play()
        self.players[sound.id] = player
        return player

    def _preload(self) -> None:
        """Load the sounds on tracks with ``preload`` now, so their first play isn't late."""
        try:
            for sound, entry in self.state.sound_files.items():
                if self.state.tracks.get(str(entry.get("track")), {}).get("preload"):
                    self._source(sound)
                    self._length(sound)
        except Exception:
            log.exception("Couldn't preload sounds; carrying on without sound")
            self.broken = True

    def _file(self, sound: str) -> str:
        return str(self.state.sound_files[sound]["file"])

    def _source(self, sound: str) -> Any:
        import pyglet

        file = self._file(sound)
        if Path(file).stat().st_size > STREAM_BYTES:
            return pyglet.media.load(file)            # a streaming source plays once: open it each time
        if sound not in self._static:
            self._static[sound] = pyglet.media.load(file, streaming=False)
        return self._static[sound]

    def _length(self, sound: str) -> float | None:
        if sound not in self._lengths:
            import pyglet
            from pyglet.media.exceptions import MediaException

            try:
                self._lengths[sound] = pyglet.media.load(self._file(sound)).duration
            except (OSError, MediaException):
                log.warning("Can't read %s; it plays until it's stopped", sound)
                self._lengths[sound] = None
        return self._lengths[sound]

    def _stop_all(self) -> None:
        for player in self.players.values():
            player.delete()
        self.players = {}
