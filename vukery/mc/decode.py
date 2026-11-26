"""Decoding sounds for pyglet: ``.wav`` with pyglet's own decoder, everything else with the ``ffmpeg`` command.

pyglet can decode ``.ogg`` and ``.mp3`` itself, through its FFmpeg binding.
With FFmpeg 8.1 on macOS (pyglet 2.1.19) that binding read the files'
length but returned no audio, so players ran in silence. The ``ffmpeg``
command decodes the same files the same way on every FFmpeg version, so
vukery runs it and hands pyglet plain 16-bit stereo PCM:

- short sounds are decoded once, into memory (``decoded``);
- long ones (music) stream from an ``ffmpeg`` pipe as they play
  (``PipeSource``), so a song doesn't sit in memory or stall a frame.
"""

import shutil
import subprocess
from typing import Any

from vukery.core.errors import VukeryError

CHANNELS, SAMPLE_BITS, SAMPLE_RATE = 2, 16, 44100
BYTES_PER_SECOND = CHANNELS * SAMPLE_BITS // 8 * SAMPLE_RATE


class SoundDecodeError(VukeryError):
    """A sound file couldn't be decoded (no ffmpeg command, or a file it can't read)."""


def uses_ffmpeg(file: str) -> bool:
    """Whether vukery decodes this file with the ffmpeg command (anything but .wav)."""
    return not file.lower().endswith(".wav")


def ffmpeg_command() -> str:
    command = shutil.which("ffmpeg")
    if command is None:
        raise SoundDecodeError("Sounds other than .wav need the ffmpeg command "
                               "(macOS: brew install ffmpeg; Debian: apt install ffmpeg)")
    return command


def _arguments(file: str, start: float = 0.0) -> list[str]:
    seek = ["-ss", f"{start:.3f}"] if start > 0 else []
    return [ffmpeg_command(), "-v", "error", "-nostdin", *seek, "-i", file, "-f", "s16le", "-acodec", "pcm_s16le",
            "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), "pipe:1"]


def decoded(file: str) -> bytes:
    """The whole file as 16-bit stereo PCM at 44.1 kHz."""
    try:
        result = subprocess.run(_arguments(file), capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        raise SoundDecodeError(f"ffmpeg couldn't decode {file}: {e.stderr.decode(errors='replace').strip()}") from e
    return result.stdout


def duration(file: str) -> float | None:
    """The file's length in seconds, from ffprobe (it comes with ffmpeg), if it can tell."""
    probe = shutil.which("ffprobe")
    if probe is None:
        return None
    result = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file],
                            capture_output=True, text=True, check=False)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def audio_format() -> Any:
    from pyglet.media.codecs.base import AudioFormat

    return AudioFormat(channels=CHANNELS, sample_size=SAMPLE_BITS, sample_rate=SAMPLE_RATE)


def memory_source(file: str) -> Any:
    """A short sound, decoded once: pyglet can play it on any number of players at once."""
    data = decoded(file)   # first: no ffmpeg, no pyglet needed
    from pyglet.media.codecs.base import StaticSource

    class Decoded(StaticSource):
        def __init__(self, data: bytes) -> None:   # pyglet's StaticSource decodes another source; this has PCM
            self.audio_format = audio_format()
            self._data = data
            self._duration = len(data) / BYTES_PER_SECOND

    return Decoded(data)


def pipe_source(file: str, length: float | None) -> Any:
    """A long sound, decoded as it plays. Each player needs its own."""
    ffmpeg_command()   # first: explain a missing ffmpeg before anything else
    from pyglet.media.codecs.base import AudioData, StreamingSource

    class PipeSource(StreamingSource):
        def __init__(self) -> None:
            self.audio_format = audio_format()
            self._duration = length
            self._process: subprocess.Popen[bytes] | None = None
            self._at = 0.0
            self._start(0.0)

        def _start(self, at: float) -> None:
            self.delete()
            self._process = subprocess.Popen(_arguments(file, at), stdout=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL)
            self._at = at

        def seek(self, timestamp: float) -> None:
            self._start(timestamp)

        def get_audio_data(self, num_bytes: float, compensation_time: float = 0.0) -> Any:
            assert self._process is not None
            stdout = self._process.stdout
            data = stdout.read(self.audio_format.align(int(num_bytes))) if stdout else b""
            if not data:
                return None
            timestamp = self._at
            self._at += len(data) / BYTES_PER_SECOND
            return AudioData(data, len(data), timestamp, len(data) / BYTES_PER_SECOND)

        def delete(self) -> None:
            if self._process is not None:
                self._process.kill()
                self._process.wait()
                if self._process.stdout:
                    self._process.stdout.close()
                self._process = None

    return PipeSource()
