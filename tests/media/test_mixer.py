"""The media controller's mixer: tracks, priorities, the queue, loops and ducking, on a hand-moved clock."""

from vukery.mc.mixer import Mixer
from vukery.testing import expect

TRACKS = {"music": {"volume": 0.5, "simultaneous_sounds": 1},
          "sfx": {"volume": 1.0, "simultaneous_sounds": 2},
          "voice": {"volume": 1.0, "simultaneous_sounds": 1}}
LENGTHS = {"song": 10.0, "ping": 1.0, "boom": 2.0, "callout": 3.0}


class Clock:
    def __init__(self):
        self.time = 0.0

    def __call__(self):
        return self.time


def _mixer():
    clock = Clock()
    return Mixer(TRACKS, clock, LENGTHS.get), clock


_ids = iter(range(1, 10_000))


def _play(mixer, sound, track="sfx", **options):
    message = {"action": "play", "id": next(_ids), "sound": sound, "track": track, "volume": 1.0, **options}
    mixer.handle(message)
    return message["id"]


def _now(mixer, clock, at):
    clock.time = at
    mixer.update()
    return sorted(p.sound for p in mixer.playing)


def describe_mixer():
    def it_plays_a_sound_until_it_ends():
        mixer, clock = _mixer()
        _play(mixer, "ping")
        expect(_now(mixer, clock, 0.5)).to_equal(["ping"])
        expect(_now(mixer, clock, 1.0)).to_equal([])

    def describe_loops():
        def it_plays_loops_plus_one_times():
            mixer, clock = _mixer()
            _play(mixer, "ping", loops=2)
            expect(_now(mixer, clock, 2.9)).to_equal(["ping"])
            expect(_now(mixer, clock, 3.0)).to_equal([])

        def it_loops_forever_until_stopped():
            mixer, clock = _mixer()
            sound = _play(mixer, "song", "music", loops=-1)
            expect(_now(mixer, clock, 1000)).to_equal(["song"])
            mixer.handle({"action": "stop", "id": sound})
            expect(_now(mixer, clock, 1000)).to_equal([])

        def it_finishes_the_pass_its_on_when_told_to_stop_looping():  # mode_end_action: stop_looping
            mixer, clock = _mixer()
            sound = _play(mixer, "boom", loops=-1)
            clock.time = 4.5                       # on its third pass
            mixer.handle({"action": "stop_looping", "id": sound})
            expect(_now(mixer, clock, 5.9)).to_equal(["boom"])
            expect(_now(mixer, clock, 6.0)).to_equal([])

        def it_starts_partway_in_the_first_time():  # start_at
            mixer, clock = _mixer()
            _play(mixer, "song", "music", start_at=8)
            expect(_now(mixer, clock, 2.0)).to_equal([])

    def describe_tracks():
        def it_plays_as_many_at_once_as_the_track_allows_and_queues_the_rest():
            mixer, clock = _mixer()
            for _ in range(3):
                _play(mixer, "ping")
            expect(len(mixer.playing)).to_equal(2)
            expect(len(mixer.queued)).to_equal(1)
            expect(_now(mixer, clock, 1.0)).to_equal(["ping"])   # the queued one, once there's room

        def it_lets_a_higher_priority_sound_stop_the_lowest():
            mixer, clock = _mixer()
            _play(mixer, "song", "music", priority=100, loops=-1)
            _play(mixer, "boom", "music", priority=200)        # MPF: multiball music over base music
            expect(_now(mixer, clock, 0.1)).to_equal(["boom"])

        def it_drops_a_sound_that_waits_longer_than_its_max_queue_time():
            mixer, clock = _mixer()
            _play(mixer, "callout", "voice")
            _play(mixer, "ping", "voice", max_queue_time=0.5)
            expect(_now(mixer, clock, 3.0)).to_equal([])

        def it_drops_a_sound_that_may_not_wait_at_all():
            mixer, _ = _mixer()
            _play(mixer, "callout", "voice")
            _play(mixer, "ping", "voice", max_queue_time=0)
            expect(mixer.queued).to_equal([])

        def it_takes_the_highest_priority_from_the_queue_first():
            mixer, clock = _mixer()
            _play(mixer, "callout", "voice", priority=10)   # higher than both: neither stops it
            _play(mixer, "ping", "voice")
            _play(mixer, "boom", "voice", priority=5)
            expect(_now(mixer, clock, 3.0)).to_equal(["boom"])

        def it_forgets_a_stopped_sound_still_in_the_queue():
            mixer, clock = _mixer()
            _play(mixer, "callout", "voice")
            waiting = _play(mixer, "ping", "voice")
            mixer.handle({"action": "stop", "id": waiting})
            expect(_now(mixer, clock, 3.0)).to_equal([])

    def describe_volume():
        def it_multiplies_the_sounds_by_the_tracks():
            mixer, _ = _mixer()
            _play(mixer, "song", "music", volume=0.8)
            expect(mixer.volume(mixer.playing[0])).to_be_close_to(0.4)

        def it_ducks_the_target_track_while_a_sound_plays():
            mixer, clock = _mixer()
            _play(mixer, "song", "music", loops=-1)
            _play(mixer, "callout", "voice", ducking={"target": "music", "attack": 1, "attenuation": 0.5,
                                                       "release_point": 1, "release": 2})
            song = next(p for p in mixer.playing if p.sound == "song")
            expect(mixer.volume(song)).to_be_close_to(0.5)          # not yet
            clock.time = 0.5
            expect(mixer.volume(song)).to_be_close_to(0.375)        # halfway down
            clock.time = 1.5
            expect(mixer.volume(song)).to_be_close_to(0.25)         # down: half of the track's 0.5
            clock.time = 2.0                                        # release_point: 1 s before the callout ends
            expect(mixer.volume(song)).to_be_close_to(0.25)
            clock.time = 3.0
            expect(mixer.volume(song)).to_be_close_to(0.375)        # halfway back up
            _now(mixer, clock, 4.0)
            expect(mixer.volume(song)).to_be_close_to(0.5)

        def it_turns_the_target_back_up_when_the_ducking_sound_is_stopped():
            mixer, clock = _mixer()
            _play(mixer, "song", "music", loops=-1)
            callout = _play(mixer, "callout", "voice", ducking={"target": "music", "attack": 0, "attenuation": 0.5,
                                                                 "release": 1})
            mixer.handle({"action": "stop", "id": callout})
            clock.time = 0.5
            song = next(p for p in mixer.playing if p.sound == "song")
            expect(mixer.volume(song)).to_be_close_to(0.375)

    def describe_joining_late():  # a media controller that connected after the sound started
        def it_starts_a_sound_partway():
            mixer, clock = _mixer()
            _play(mixer, "song", "music", elapsed=4, start_at=1)
            expect(mixer.position(mixer.playing[0])).to_equal(5.0)
            expect(_now(mixer, clock, 4.9)).to_equal(["song"])
            expect(_now(mixer, clock, 5.0)).to_equal([])   # 9 s from 1 s in, and it started 4 s before we joined

        def it_finds_its_place_in_a_loop():
            mixer, _ = _mixer()
            _play(mixer, "boom", loops=-1, elapsed=5.5)
            expect(mixer.position(mixer.playing[0])).to_be_close_to(1.5)

        def it_skips_a_sound_thats_already_over():
            mixer, clock = _mixer()
            _play(mixer, "ping", elapsed=3)
            expect(_now(mixer, clock, 0)).to_equal([])

    def it_waits_for_a_stop_when_it_doesnt_know_a_sounds_length():
        clock = Clock()
        mixer = Mixer(TRACKS, clock)
        sound = _play(mixer, "mystery")
        expect(_now(mixer, clock, 100)).to_equal(["mystery"])
        mixer.handle({"action": "stop_looping", "id": sound})   # without a length, it can't tell where a pass ends
        mixer.handle({"action": "stop", "id": sound})
        expect(_now(mixer, clock, 100)).to_equal([])

    def it_ignores_messages_it_doesnt_know():
        mixer, _ = _mixer()
        mixer.handle({"action": "pause", "id": 1})
        expect(mixer.playing).to_equal([])
