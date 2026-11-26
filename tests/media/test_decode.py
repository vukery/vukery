"""Decoding sounds with the ffmpeg command: real audio in, 16-bit stereo PCM out."""

import array
import math
import shutil
import struct
import subprocess
import wave

import pytest

from vukery.mc import decode
from vukery.testing import expect

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="the ffmpeg command isn't installed")


@pytest.fixture
def tone(tmp_path):
    """Two seconds of a 440 Hz tone, as .wav and (with ffmpeg) .flac."""
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(16000 * math.sin(2 * math.pi * 440 * i / 22050)))
                               for i in range(44100)))
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-c:a", "flac", str(tmp_path / "tone.flac")],
                       check=True)
    return tmp_path


def _peak(data):
    return max(abs(sample) for sample in array.array("h", bytes(data)))


def describe_decoding():
    def it_leaves_wav_files_to_pyglet():
        expect(decode.uses_ffmpeg("a.wav")).to_be_false()
        expect(decode.uses_ffmpeg("a.OGG")).to_be_true()

    @needs_ffmpeg
    def it_decodes_a_whole_file_to_16_bit_stereo(tone):
        data = decode.decoded(str(tone / "tone.flac"))
        expect(len(data) / decode.BYTES_PER_SECOND).to_be_close_to(2.0, within=0.05)
        expect(_peak(data)).to_be_greater_than(10_000)    # real sound, not silence

    @needs_ffmpeg
    def it_tells_a_files_length(tone):
        expect(decode.duration(str(tone / "tone.flac"))).to_be_close_to(2.0, within=0.05)

    @needs_ffmpeg
    def it_makes_a_source_any_number_of_players_can_play(tone):
        source = decode.memory_source(str(tone / "tone.flac"))
        expect(source.duration).to_be_close_to(2.0, within=0.05)
        expect(_peak(source.get_queue_source().get_audio_data(50_000).data)).to_be_greater_than(10_000)

    @needs_ffmpeg
    def it_streams_a_long_file_from_where_its_told(tone):
        source = decode.pipe_source(str(tone / "tone.flac"), 2.0)
        try:
            source.seek(1.5)
            first = source.get_audio_data(400_000)
            expect(first.timestamp).to_equal(1.5)
            expect(len(first.data) / decode.BYTES_PER_SECOND).to_be_close_to(0.5, within=0.05)  # what's left
            expect(source.get_audio_data(400_000)).to_be_none()
        finally:
            source.delete()

    @needs_ffmpeg
    def it_explains_a_file_it_cant_decode(tmp_path):
        broken = tmp_path / "broken.ogg"
        broken.write_bytes(b"not audio")
        with pytest.raises(decode.SoundDecodeError, match="couldn't decode"):
            decode.decoded(str(broken))

    def it_asks_for_the_ffmpeg_command_when_it_isnt_there(monkeypatch):
        monkeypatch.setattr(decode.shutil, "which", lambda _name: None)
        with pytest.raises(decode.SoundDecodeError, match="need the ffmpeg command"):
            decode.ffmpeg_command()
        expect(decode.duration("x.ogg")).to_be_none()
