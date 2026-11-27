# Sound

!!! note "0.0.x"
    Sounds, sound pools and tracks, played by modes, mixed with MPF's rules
    (priorities, queueing, loops, ducking) and played by the pyglet media
    controller. Sounds in shows, fades, markers and the other MPF sound
    settings come later; vukery stops with an error if your config uses one.

## Sound files

**Every file in `assets/sounds/` is a sound,** named by its file name without
the extension: `assets/sounds/explosion.ogg` is the sound `explosion`. Use
`.ogg`, `.wav`, `.mp3` or `.flac`. vukery decodes everything but `.wav` with
the `ffmpeg` command (see [Getting started](../getting-started/index.md)): short
sounds once, into memory, and music as it plays. `vuk health` says whether
`ffmpeg` is there; without it, only `.wav` sounds play.

## Playing a sound

A mode plays a sound, or one of a pool's (MPF: `sound_player`):

```python
from vukery import Mode, on


class Base(Mode):
    @on.switch("s_bumper_1")
    def bumper(self):
        self.play_sound("bullet_ping_pool")

    def mode_start(self, **_):
        self.play_sound("base_bgm", start_at=50)   # 50 seconds into the file
```

| Option | | MPF `sound_player` |
|---|---|---|
| `volume` | replaces the sound's volume | `volume` |
| `loops` | replaces its loops: `0` once, `-1` forever, `2` three times | `loops` |
| `priority` | added to its priority | `priority` |
| `start_at` | seconds into the file, the first time through | `start_at` |
| `delay` | seconds to wait before playing | `delay` |
| `max_queue_time` | replaces its `max_queue_time` | `max_queue_time` |

`self.stop_sound("base_bgm")` stops it (or whatever a pool played under its
name). **When a mode stops, its sounds stop** or finish the loop they're on,
as each sound's `mode_end_action` says, and its delayed sounds don't play.

## Settings (YAML)

Sound settings are asset settings, so they're YAML, in MPF's sections and with
MPF's names.

```yaml
sound_system:
  tracks:
    music:
      volume: 0.4
      simultaneous_sounds: 1
    sfx:
      volume: 0.6
      simultaneous_sounds: 6
    voice:
      volume: 0.8
      simultaneous_sounds: 1

sounds:
  base_bgm:
    file: base_bgm.ogg        # in assets/sounds/; leave it out when the name is the file name
    track: music
    volume: 0.7
    loops: -1
    priority: 100
    mode_end_action: stop
  flash_score:
    file: flash-score-steve-it.ogg
    track: voice
    max_queue_time: 0.5s
    ducking:
      target: music
      attenuation: -5db
      release_point: 1s
      release: 6s

sound_pools:
  shot_and_ping_pool:
    type: random
    sounds:
      - gun_shot_distant_sfx|5    # weighs the pick: 5 times as likely as a weight of 1
      - bullet_ping_1_sfx
```

### Tracks (`sound_system: tracks:`)

| Setting | Default | |
|---|---|---|
| `volume` | `0.5` | 0.0 to 1.0, or decibels: `-6db` |
| `simultaneous_sounds` | `8` | how many sounds it plays at once |
| `preload` | `false` | load its sounds when the media controller connects, so their first play isn't late |

Without tracks, there's one: `sfx`. A sound plays on `sfx` unless it says
otherwise (or on the first track, if there's no `sfx`). `buffer`,
`frequency` and `channels` are accepted and left to pyglet.

### Sounds (`sounds:`)

| Setting | Default | |
|---|---|---|
| `file` | the sound's name | the file in `assets/sounds/` |
| `track` | `sfx` | |
| `volume` | `0.5` | 0.0 to 1.0, or decibels: `-6db` |
| `priority` | `0` | decides who plays when a track is full |
| `loops` | `0` | `0` once, `-1` forever, `2` three times |
| `max_queue_time` | none (waits) | how long it may wait for a full track; `0`: play now or not at all |
| `mode_end_action` | `stop_looping` | `stop`, or `stop_looping` to finish the pass it's on |
| `ducking` | | turns another track down while it plays, below |

### Ducking

| Setting | Default | |
|---|---|---|
| `target` | (required) | the track to turn down |
| `attack` | `10ms` | how long turning it down takes |
| `attenuation` | `1.0` | how far down: a volume or decibels (`-5db`) |
| `release_point` | `0` | how long before the sound ends to start turning it back up |
| `release` | `10ms` | how long turning it back up takes |

### Pools (`sound_pools:`)

`type: random` picks one of its `sounds` each time (`name|3` weighs a sound),
and `type: sequence` plays them in turn. The pool's `track` is accepted;
each sound plays on its own track.

## How sounds are mixed

The engine decides what to play: a pool's pick, delays, and what stops when a
mode stops. The media controller mixes, as MPF's does:

- **A full track:** a new sound with a higher priority stops the
  lowest-priority sound playing; otherwise it waits up to its
  `max_queue_time`, and the highest priority waiting plays next.
- **Volume** is the sound's, times its track's, times any ducking.

**Who plays sound:** in `vuk me`, the dashboard. With `vuk us`, the first
display's media controller (`python -m vukery.mc . --display main --audio`),
or, for a machine without displays, one that only plays sound.

## Testing sounds

Specs check what was played, without a sound card:

```python
def it_pings_on_the_bumpers(game):
    game.start_game()
    game.switch("s_bumper_1")
    expect(game).to_have_played("bullet_ping_pool")     # any of the pool's sounds
    expect(game).not_to_have_played("base_bgm")
    expect(game.sounds()).to_equal(["bullet_ping_2_sfx"])  # what was picked, in order
```

`expect(game).to_have_played("name", times=2)` counts. `game.machine.media.random.seed(1)`
makes pool picks repeat from run to run.

## Coming from MPF

| MPF | vukery |
|---|---|
| `sounds:`, `sound_pools:`, `sound_system: tracks:` | the same sections and settings (the ones above) |
| `sound_player: event: sound_name` | `self.play_sound("sound_name")` in a handler |
| `sound_player` `action: stop` | `self.stop_sound("sound_name")` |
| `sound_player` `{condition}` | an `if` in the handler |
| `assets: sounds:` and `sounds/` folders | `assets/sounds/`, every file a sound |
| track `events_when_played` and other track events | not yet |
| `fade_in`, `fade_out`, `markers`, `simultaneous_limit`, `key` | not yet |
| pool types `random_force_next`, `random_force_all` | not yet |
