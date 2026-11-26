"""The audio output, with a stand-in for pyglet: what it starts, how loud, and what it stops."""

import importlib.machinery
import sys
import types

import pytest

from vukery.mc.audio import Audio
from vukery.mc.state import MediaState
from vukery.testing import expect


class Player:
    def __init__(self):
        self.queued, self.volume, self.loop, self.at, self.playing, self.deleted = None, None, False, 0.0, False, False

    def queue(self, source):
        self.queued = source

    def seek(self, seconds):
        self.at = seconds

    def play(self):
        self.playing = True

    def delete(self):
        self.deleted = True


class Source:
    def __init__(self, file, streaming=True):
        self.file, self.streaming, self.duration = file, streaming, 2.0


@pytest.fixture
def pyglet(monkeypatch):
    fake, media, exceptions = (types.ModuleType(name) for name in ("pyglet", "pyglet.media",
                                                                   "pyglet.media.exceptions"))
    exceptions.MediaException = type("MediaException", (Exception,), {})
    media.Player, media.load, media.exceptions = Player, Source, exceptions
    fake.media = media
    for name, module in (("pyglet", fake), ("pyglet.media", media), ("pyglet.media.exceptions", exceptions)):
        module.__spec__ = importlib.machinery.ModuleSpec(name, None)   # so tools that inspect modules don't trip
        monkeypatch.setitem(sys.modules, name, module)
    return fake


class Clock:
    def __init__(self):
        self.time = 0.0

    def __call__(self):
        return self.time


def _connected(tmp_path):
    (tmp_path / "boom.wav").write_bytes(b"x")
    clock = Clock()
    state = MediaState(now=clock, audio=True)
    state.apply({"type": "welcome", "tracks": {"sfx": {"volume": 0.5, "simultaneous_sounds": 8}},
                 "sounds": {"boom": {"file": str(tmp_path / "boom.wav"), "track": "sfx"}}})
    return state, clock


def _welcome(state):
    return {"type": "welcome", "sounds": state.sound_files}


def _play(state, sound_id, **options):
    state.apply({"type": "sound", "action": "play", "id": sound_id, "sound": "boom", "name": "boom", "track": "sfx",
                 "volume": 0.8} | options)


def describe_audio():
    def it_plays_what_the_mixer_says_at_the_mixed_volume(pyglet, tmp_path):
        state, _ = _connected(tmp_path)
        audio = Audio(state)
        _play(state, 1, start_at=0.5, loops=-1)
        audio.frame()
        player = audio.players[1]
        expect((player.playing, player.loop, player.at)).to_equal((True, True, 0.5))
        expect(player.volume).to_be_close_to(0.4)          # 0.8 times the track's 0.5
        expect(player.queued.streaming).to_be_false()      # a small file: decoded once

    def it_stops_a_player_when_the_sound_ends(pyglet, tmp_path):
        state, clock = _connected(tmp_path)
        audio = Audio(state)
        _play(state, 1)
        audio.frame()
        player = audio.players[1]
        clock.time = 2.0                                   # the stand-in's sounds are 2 seconds long
        audio.frame()
        expect(player.deleted).to_be_true()
        expect(audio.players).to_equal({})

    def it_loads_the_sounds_of_preload_tracks_when_it_connects(pyglet, tmp_path):
        state, _ = _connected(tmp_path)
        state.apply({**_welcome(state), "tracks": {"sfx": {"volume": 0.5, "simultaneous_sounds": 8, "preload": True}}})
        audio = Audio(state)
        audio.frame()
        expect(list(audio._static)).to_equal(["boom"])

    def it_picks_up_whats_already_playing_when_it_connects(pyglet, tmp_path):
        state, clock = _connected(tmp_path)
        clock.time = 10
        state.apply({**_welcome(state), "tracks": {"sfx": {"volume": 0.5}},
                     "playing": [{"type": "sound", "action": "play", "id": 7, "sound": "boom", "name": "boom",
                                  "track": "sfx", "volume": 1.0, "loops": -1, "elapsed": 3.5}]})
        audio = Audio(state)
        audio.frame()
        expect(audio.players[7].at).to_be_close_to(1.5)   # 3.5 s into a 2 s loop
        expect(list(state.played)).to_equal([])           # not played again, as far as specs go

    def it_skips_a_sound_it_cant_decode_and_plays_the_rest(pyglet, tmp_path, monkeypatch):
        from vukery.mc import decode

        state, _ = _connected(tmp_path)
        (tmp_path / "song.ogg").write_bytes(b"x")
        state.sound_files["song"] = {"file": str(tmp_path / "song.ogg"), "track": "sfx"}
        monkeypatch.setattr(decode.shutil, "which", lambda _name: None)   # no ffmpeg command
        audio = Audio(state)
        _play(state, 1, sound="song")
        _play(state, 2)
        audio.frame()
        expect(sorted(audio.players)).to_equal([2])   # the .wav still plays
        expect(audio.broken).to_be_false()

    def it_waits_for_the_engine(pyglet):
        audio = Audio(MediaState(audio=True))
        audio.frame()
        expect(audio.mixer).to_be_none()

    def it_carries_on_quietly_when_sound_output_fails(pyglet, tmp_path, monkeypatch):
        state, _ = _connected(tmp_path)
        audio = Audio(state)

        def broken():
            raise RuntimeError("no sound card")

        monkeypatch.setattr(pyglet.media, "Player", broken)
        _play(state, 1)
        audio.frame()
        expect(audio.broken).to_be_true()
        _play(state, 2)
        audio.frame()                                      # and stays quiet
        expect(audio.players).to_equal({})
