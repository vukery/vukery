"""Sounds: what the machine can play, from ``assets/sounds/`` and MPF's sound sections.

- **Every file in ``assets/sounds/``** is a sound, named by its file name
  without the extension (``assets/sounds/explosion.ogg`` is ``explosion``).
- **``sounds:``** gives a sound settings, or a name of its own for a file
  (MPF's section: ``file``, ``track``, ``volume``, ``priority``, ``loops``,
  ``max_queue_time``, ``mode_end_action``, ``ducking``).
- **``sound_pools:``** groups sounds; playing a pool plays one of them
  (``type: random`` or ``sequence``; ``name|3`` weighs a random pick).
- **``sound_system: tracks:``** are the channels sounds play on, each with a
  volume and how many sounds it plays at once (``simultaneous_sounds``).

The engine decides what to play (a pool's pick, delays, what stops when a
mode stops) and tells the media controller, which mixes: track limits,
priorities, queueing, loops and ducking, since those depend on how long each
sound is.
"""

import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vukery.core.errors import ConfigError
from vukery.core.shows import seconds
from vukery.core.yaml_values import mapping

AUDIO_FILES = (".ogg", ".wav", ".mp3", ".flac", ".m4a", ".aac")
MODE_END_ACTIONS = ("stop", "stop_looping")
POOL_TYPES = ("random", "sequence")
SOUND_SETTINGS = {"file", "track", "volume", "priority", "loops", "max_queue_time", "mode_end_action", "ducking"}
DUCKING_SETTINGS = {"target", "attack", "attenuation", "release_point", "release"}
TRACK_SETTINGS = {"volume", "simultaneous_sounds", "preload"}
POOL_SETTINGS = {"sounds", "type", "track"}
SYSTEM_SETTINGS = {"tracks", "buffer", "frequency", "channels"}  # the last three: pyglet picks these itself


def _volume(value: Any, where: str) -> float:
    """``0.5``, or decibels as MPF writes them: ``-5db`` (a gain: 0 dB is full volume)."""
    match value:
        case bool():
            raise ConfigError(f"{where}: expected a volume, got {value!r}")
        case int() | float():
            number = float(value)
        case str() as text if text.strip().lower().endswith("db"):
            try:
                number = 10 ** (float(text.strip()[:-2]) / 20)
            except ValueError:
                raise ConfigError(f"{where}: {value!r} isn't a volume (e.g. 0.5 or -5db)") from None
        case _:
            raise ConfigError(f"{where}: {value!r} isn't a volume (e.g. 0.5 or -5db)")
    if not 0 <= number <= 1:
        raise ConfigError(f"{where}: a volume is from 0.0 to 1.0, not {value!r}")
    return number


def _unsupported(data: dict[str, Any], known: set[str], where: str) -> None:
    unknown = sorted(set(data) - known)
    if unknown:
        raise ConfigError(f"{where}: not supported yet: {', '.join(unknown)}")


@dataclass(frozen=True)
class Track:
    name: str
    volume: float = 0.5
    simultaneous_sounds: int = 8
    preload: bool = False   # load its sounds when the media controller connects, not when first played


@dataclass(frozen=True)
class Ducking:
    """While a sound plays, turn another track down (MPF's ``ducking:``)."""

    target: str
    attack: float = 0.01          # seconds to turn it down
    attenuation: float = 1.0      # how far down: a volume (0.5) or decibels (-5db)
    release_point: float = 0.0    # seconds before the sound ends to start turning it back up
    release: float = 0.01         # seconds to turn it back up


@dataclass(frozen=True)
class Sound:
    name: str
    file: str                     # the full path
    track: str
    volume: float = 0.5
    priority: int = 0
    loops: int = 0                # 0 plays once, -1 forever, 2 plays three times
    max_queue_time: float | None = None   # how long it may wait for its track; None: as long as it takes
    mode_end_action: str = "stop_looping"
    ducking: Ducking | None = None


@dataclass(frozen=True)
class Pool:
    name: str
    sounds: tuple[str, ...]
    weights: tuple[int, ...]
    type: str = "random"


@dataclass
class Sounds:
    tracks: dict[str, Track]
    sounds: dict[str, Sound]
    pools: dict[str, Pool]

    @classmethod
    def load(cls, game_dir: Path, system: dict[str, Any], sounds: dict[str, Any], pools: dict[str, Any]) -> Sounds:
        _unsupported(system, SYSTEM_SETTINGS, "sound_system")
        tracks = {name: _track(str(name), mapping(entry, f"sound_system: tracks: {name}"))
                  for name, entry in mapping(system.get("tracks"), "sound_system: tracks").items()}
        if not tracks:
            tracks = {"sfx": Track("sfx")}   # one track when none are configured
        default_track = "sfx" if "sfx" in tracks else next(iter(tracks))
        folder = game_dir / "assets" / "sounds"
        files = {p.stem: p for p in sorted(folder.iterdir()) if p.suffix.lower() in AUDIO_FILES} \
            if folder.is_dir() else {}
        found = {name: Sound(name, str(path), default_track) for name, path in files.items()}
        for name, entry in sounds.items():
            found[str(name)] = _sound(str(name), mapping(entry, f"sounds: {name}"), folder, files, tracks,
                                      default_track)
        loaded = cls(tracks, found, {})
        for name, entry in pools.items():
            loaded.pools[str(name)] = _pool(str(name), mapping(entry, f"sound_pools: {name}"), loaded)
        return loaded

    def resolve(self, name: str, rng: random.Random, turn: dict[str, int]) -> Sound:
        """The sound to play for ``name``: the sound itself, or a pool's pick."""
        if name in self.sounds:
            return self.sounds[name]
        pool = self.pools.get(name)
        if pool is None:
            raise ConfigError(f"No sound or sound pool named {name!r} (sounds are the files in assets/sounds/, "
                              "plus sounds: and sound_pools:)")
        match pool.type:
            case "sequence":
                index = turn.get(name, 0)
                turn[name] = (index + 1) % len(pool.sounds)
                return self.sounds[pool.sounds[index]]
            case _:
                return self.sounds[rng.choices(pool.sounds, weights=pool.weights)[0]]

    def to_data(self) -> dict[str, Any]:
        """What a media controller needs: the tracks, and each sound's file."""
        return {"tracks": {name: asdict(track) for name, track in self.tracks.items()},
                "sounds": {name: {"file": sound.file, "track": sound.track} for name, sound in self.sounds.items()}}


def _track(name: str, data: dict[str, Any]) -> Track:
    where = f"sound_system: tracks: {name}"
    _unsupported(data, TRACK_SETTINGS, where)
    limit = int(data.get("simultaneous_sounds", 8))
    if limit < 1:
        raise ConfigError(f"{where}: simultaneous_sounds must be 1 or more")
    return Track(name, _volume(data.get("volume", 0.5), f"{where}: volume"), limit, bool(data.get("preload", False)))


def _sound(name: str, data: dict[str, Any], folder: Path, files: dict[str, Path], tracks: dict[str, Track],
           default_track: str) -> Sound:
    where = f"sounds: {name}"
    _unsupported(data, SOUND_SETTINGS, where)
    file = data.get("file")
    if file is not None:
        path = folder / str(file)
        if not path.is_file():
            raise ConfigError(f"{where}: no file {file!r} in assets/sounds/")
    elif name in files:
        path = files[name]
    else:
        raise ConfigError(f"{where}: no file named {name} in assets/sounds/ (or give it a file:)")
    track = str(data.get("track", default_track))
    if track not in tracks:
        raise ConfigError(f"{where}: no track named {track!r} (sound_system: tracks: {', '.join(tracks)})")
    action = str(data.get("mode_end_action", "stop_looping"))
    if action not in MODE_END_ACTIONS:
        raise ConfigError(f"{where}: mode_end_action is {' or '.join(MODE_END_ACTIONS)}, not {action!r}")
    queue = data.get("max_queue_time")
    ducking = mapping(data.get("ducking"), f"{where}: ducking") if data.get("ducking") is not None else None
    return Sound(name, str(path), track, _volume(data.get("volume", 0.5), f"{where}: volume"),
                 int(data.get("priority", 0)), int(data.get("loops", 0)),
                 None if queue is None else seconds(queue, f"{where}: max_queue_time"), action,
                 None if ducking is None else _ducking(ducking, f"{where}: ducking", tracks))


def _ducking(data: dict[str, Any], where: str, tracks: dict[str, Track]) -> Ducking:
    _unsupported(data, DUCKING_SETTINGS, where)
    target = str(data.get("target", ""))
    if target not in tracks:
        raise ConfigError(f"{where}: target must be a track ({', '.join(tracks)}), not {target!r}")
    return Ducking(target, seconds(data.get("attack", 0.01), f"{where}: attack"),
                   _volume(data.get("attenuation", 1.0), f"{where}: attenuation"),
                   seconds(data.get("release_point", 0), f"{where}: release_point"),
                   seconds(data.get("release", 0.01), f"{where}: release"))


def _pool(name: str, data: dict[str, Any], loaded: Sounds) -> Pool:
    where = f"sound_pools: {name}"
    _unsupported(data, POOL_SETTINGS, where)
    kind = str(data.get("type", "random"))
    if kind not in POOL_TYPES:
        raise ConfigError(f"{where}: type {kind!r} isn't supported yet ({', '.join(POOL_TYPES)})")
    entries: list[Any] = data.get("sounds") or []
    if isinstance(entries, str):
        entries = [part.strip() for part in entries.split(",")]
    members: list[str] = []
    weights: list[int] = []
    for entry in entries:
        sound, _, weight = str(entry).partition("|")
        if sound not in loaded.sounds:
            raise ConfigError(f"{where}: no sound named {sound!r}")
        members.append(sound)
        weights.append(int(weight) if weight else 1)
    if not members:
        raise ConfigError(f"{where}: list its sounds")
    return Pool(name, tuple(members), tuple(weights), kind)
