"""Sounds: assets/sounds/ files, MPF's sounds:, sound_pools: and sound_system:, played by modes."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.testing import GameRig, expect

FILES = {f"assets/sounds/{name}": "not really audio: the engine only needs the file"
         for name in ("ping_1.ogg", "ping_2.ogg", "music.ogg", "callout.wav", "boom.ogg")}


def _sound_config(config):
    config["sound_system"] = {"tracks": {"music": {"volume": 0.4, "simultaneous_sounds": 1},
                                         "sfx": {"volume": 0.6, "simultaneous_sounds": 6},
                                         "voice": {"volume": 0.8, "simultaneous_sounds": 1}}}
    config["sounds"] = {
        "base_bgm": {"file": "music.ogg", "track": "music", "volume": 0.7, "loops": -1, "priority": 100,
                     "mode_end_action": "stop"},
        "callout": {"track": "voice", "volume": 0.9, "max_queue_time": "500ms",
                    "ducking": {"target": "music", "attenuation": "-6db", "release_point": "1s", "release": 6}},
    }
    config["sound_pools"] = {"pings": {"type": "random", "sounds": ["ping_1|3", "ping_2"]},
                             "in_turn": {"type": "sequence", "sounds": "ping_1, ping_2"}}


@pytest.fixture
def game(tmp_path):
    rig = GameRig(basic_machine(tmp_path, edit=_sound_config, files=FILES))
    rig.messages = []
    rig.machine.media.attach(rig.messages.append)
    rig.start_game()
    yield rig
    rig.stop()


def _base(game):
    return game.mode("base")


def _sent(game, action):
    return [m for m in game.messages if m.get("type") == "sound" and m["action"] == action]


def describe_sounds():
    def it_makes_every_file_in_assets_sounds_a_sound(game):
        expect(sorted(game.machine.sounds.sounds)).to_equal(
            ["base_bgm", "boom", "callout", "music", "ping_1", "ping_2"])

    def it_tells_media_controllers_the_tracks_and_files(game):
        welcome = game.messages[0]
        expect(welcome["tracks"]["sfx"]).to_equal({"name": "sfx", "volume": 0.6, "simultaneous_sounds": 6,
                                                   "preload": False})
        expect(welcome["sounds"]["base_bgm"]["file"]).to_contain("music.ogg")

    def it_tells_a_media_controller_that_connects_late_whats_playing(game):
        _base(game).play_sound("base_bgm")
        game.advance(3)
        playing = game.machine.media.welcome()["playing"]
        expect([(p["sound"], round(p["elapsed"], 3)) for p in playing]).to_equal([("base_bgm", 3.0)])

    def it_forgets_what_a_mode_played_when_it_stops(game):
        _base(game).play_sound("base_bgm")
        game.drain()
        expect([p["sound"] for p in game.machine.media.welcome()["playing"]]).not_to_contain("base_bgm")

    def it_plays_a_sound_with_its_settings(game):
        _base(game).play_sound("base_bgm", start_at=50)
        played = game.display.played[-1]
        expect({k: played[k] for k in ("sound", "track", "volume", "loops", "priority", "start_at")}).to_equal(
            {"sound": "base_bgm", "track": "music", "volume": 0.7, "loops": -1, "priority": 100, "start_at": 50})
        expect(game).to_have_played("base_bgm", times=1)

    def it_takes_mpfs_sound_player_options(game):
        _base(game).play_sound("boom", volume=0.2, loops=2, priority=5, max_queue_time=0)
        played = game.display.played[-1]
        expect((played["volume"], played["loops"], played["priority"], played["max_queue_time"])).to_equal(
            (0.2, 2, 5, 0))

    def it_reads_decibels_and_ducking(game):
        played = game.machine.sounds.sounds["callout"]
        expect(played.max_queue_time).to_equal(0.5)
        expect(played.ducking.attenuation).to_be_close_to(0.501, within=0.001)   # -6 dB
        expect((played.ducking.release_point, played.ducking.release)).to_equal((1.0, 6.0))

    def it_waits_for_a_delay(game):
        _base(game).play_sound("callout", delay=0.5)
        expect(game).not_to_have_played("callout")
        game.advance(0.5)
        expect(game).to_have_played("callout")

    def describe_pools():
        def it_plays_one_of_a_pools_sounds(game):
            game.machine.media.random.seed(2)   # the same picks every run
            for _ in range(20):
                _base(game).play_sound("pings")
            expect(game).to_have_played("pings", times=20)
            expect(set(game.sounds())).to_equal({"ping_1", "ping_2"})

        def it_weighs_a_random_pick(game):
            game.machine.media.random.seed(1)
            for _ in range(400):
                _base(game).play_sound("pings")
            expect(game.times_played("ping_1")).to_be_greater_than(250)   # 3 to 1: about 300

        def it_plays_a_sequence_in_turn(game):
            for _ in range(3):
                _base(game).play_sound("in_turn")
            expect(game.sounds()).to_equal(["ping_1", "ping_2", "ping_1"])

    def describe_stopping():
        def it_stops_a_sound_or_a_pools_by_name(game):
            _base(game).play_sound("pings")
            _base(game).play_sound("base_bgm")
            _base(game).stop_sound("pings")
            expect(len(_sent(game, "stop"))).to_equal(1)

        def it_stops_or_finishes_a_modes_sounds_when_it_stops(game):  # mode_end_action
            _base(game).play_sound("base_bgm")      # mode_end_action: stop
            _base(game).play_sound("boom")          # the default: stop_looping
            game.drain()
            expect(len(_sent(game, "stop"))).to_equal(1)
            expect(len(_sent(game, "stop_looping"))).to_equal(1)

        def it_forgets_a_delayed_sound_when_the_mode_stops(game):
            _base(game).play_sound("callout", delay=2)
            game.drain()
            game.advance(3)
            expect(game).not_to_have_played("callout")


def describe_sound_config():
    @pytest.mark.parametrize(("edit", "message"), [
        (lambda c: c["sounds"].update(boom={"fade_in": 1}), "not supported yet: fade_in"),
        (lambda c: c["sounds"].update(nope={"track": "sfx"}), "no file named nope"),
        (lambda c: c["sounds"].update(boom={"file": "missing.ogg"}), "no file 'missing.ogg'"),
        (lambda c: c["sounds"].update(boom={"track": "drums"}), "no track named 'drums'"),
        (lambda c: c["sounds"].update(boom={"volume": 2}), "from 0.0 to 1.0"),
        (lambda c: c["sounds"].update(boom={"volume": "loud"}), "isn't a volume"),
        (lambda c: c["sounds"].update(boom={"mode_end_action": "fade"}), "stop or stop_looping"),
        (lambda c: c["sounds"].update(boom={"ducking": {"target": "drums"}}), "target must be a track"),
        (lambda c: c["sound_pools"].update(bad={"sounds": ["nope"]}), "no sound named 'nope'"),
        (lambda c: c["sound_pools"].update(bad={"type": "random_force_all", "sounds": ["boom"]}), "isn't supported"),
        (lambda c: c["sound_pools"].update(bad={"sounds": []}), "list its sounds"),
        (lambda c: c["sound_system"]["tracks"]["sfx"].update(events_when_played="x"), "not supported yet"),
        (lambda c: c["sound_system"]["tracks"]["sfx"].update(simultaneous_sounds=0), "1 or more"),
    ])
    def it_explains_a_mistake(tmp_path, edit, message):
        def change(config):
            _sound_config(config)
            edit(config)

        with pytest.raises(ConfigError, match=message):
            GameRig(basic_machine(tmp_path, edit=change, files=FILES))

    def it_explains_a_sound_that_doesnt_exist(tmp_path):
        rig = GameRig(basic_machine(tmp_path, edit=_sound_config, files=FILES))
        try:
            rig.start_game()
            with pytest.raises(ConfigError, match="No sound or sound pool named 'nope'"):
                rig.mode("base").play_sound("nope")
        finally:
            rig.stop()

    def it_uses_one_track_when_none_are_configured(tmp_path):
        rig = GameRig(basic_machine(tmp_path, files={"assets/sounds/boom.ogg": "x"}))
        try:
            expect(list(rig.machine.sounds.tracks)).to_equal(["sfx"])
            expect(rig.machine.media).not_to_be_none()   # sounds alone bring the media server up
        finally:
            rig.stop()

    def it_has_nothing_to_play_without_sounds(tmp_path):
        rig = GameRig(basic_machine(tmp_path))
        try:
            rig.start_game()
            expect(rig.machine.plays_sound()).to_be_false()
            with pytest.raises(ConfigError, match="No sound or sound pool named 'boom'"):
                rig.mode("base").play_sound("boom")
        finally:
            rig.stop()
