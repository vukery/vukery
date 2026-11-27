"""Ball saves (MPF's ball_saves: device): the scenarios follow MPF's test_BallSave.py."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.devices.ball_save import BallSaveConfig
from vukery.testing import GameRig, expect

SAVES = {
    # COMBAT's: on when the ball starts, the clock starts when the ball is in play
    "default": {"active_time": "10s", "hurry_up_time": "2s", "grace_period": "2s", "enable_events": "mode_base_started",
                "timer_start_events": "sw_playfield_active", "auto_launch": False, "balls_to_save": 1},
    # Futurama's kind: two balls, enabled by a game event, the clock running at once
    "pazuzu": {"active_time": "+50s", "hurry_up_time": "10s", "enable_events": "start_pazuzu", "balls_to_save": 2},
    "unlimited": {"active_time": 0, "enable_events": "start_unlimited", "balls_to_save": -1},
    "last_ball": {"active_time": "10s", "enable_events": "start_last_ball", "only_last_ball": True},
}


def _edit(saves):
    def edit(config):
        config["switches"]["s_target"]["tags"] = "playfield_active"
        config["ball_saves"] = saves
    return edit


@pytest.fixture
def game(tmp_path):
    rig = GameRig(basic_machine(tmp_path, edit=_edit({"default": SAVES["default"]})))
    rig.start_game()
    yield rig
    rig.stop()


def _save(game, name="default"):
    return game.machine.ball_saves[name]


def describe_a_ball_save():
    def it_is_enabled_by_its_events(game):
        expect(_save(game).enabled).to_be_true()
        expect(game).to_have_posted("ball_save_default_enabled", times=1)

    def it_saves_a_drained_ball_and_serves_another(game):  # MPF: test_ball_save
        game.switch("s_target")
        game.drain()
        expect(game).to_have_posted("ball_save_default_saving_ball", times=1)
        expect(game.player.ball).to_equal(1)                   # the same ball goes on
        expect(game.game.balls_in_play).to_equal(1)
        expect(game.machine.trough().balls).to_equal(2)        # a new one was served

    def it_saves_only_as_many_balls_as_it_has(game):
        game.switch("s_target")
        game.drain()
        expect(_save(game).enabled).to_be_false()              # one save, used
        game.drain()
        expect(game.player.ball).to_equal(2)

    def it_waits_for_the_ball_to_be_in_play_before_the_clock_starts(game):
        game.advance(30)
        expect(_save(game).enabled).to_be_true()               # no playfield switch yet: no clock
        expect(game).not_to_have_posted("ball_save_default_timer_start")

    def describe_its_clock():  # MPF: test_ball_save_timer
        def it_hurries_up_then_gives_grace_then_ends(game):
            game.switch("s_target")
            expect(game).to_have_posted("ball_save_default_timer_start", times=1)
            game.advance(7.9)
            expect(_save(game).state).to_equal("enabled")
            game.advance(0.2)
            expect(_save(game).state).to_equal("hurry_up")        # 2 s before the end
            game.advance(2)
            expect(_save(game).state).to_equal("grace_period")    # still saving, lights off
            expect(_save(game).enabled).to_be_true()
            game.advance(2)
            expect(_save(game).enabled).to_be_false()
            game.drain()
            expect(game.player.ball).to_equal(2)

        def it_still_saves_in_the_grace_period(game):
            game.switch("s_target")
            game.advance(11)
            game.drain()
            expect(game.player.ball).to_equal(1)

    def it_ends_with_the_ball(game):  # disable_events: ball_will_end
        game.switch("s_target")
        game.machine.game.end_ball()
        game.advance()
        expect(game).to_have_posted("ball_save_default_disabled")

    def it_doesnt_save_a_tilted_ball(tmp_path):
        def edit(config):
            _edit({"default": SAVES["default"]})(config)
            config["switches"]["s_tilt"] = {"number": "41", "tags": "tilt"}
            config["modes"] = [*config["modes"], "tilt"]

        rig = GameRig(basic_machine(tmp_path, edit=edit))
        try:
            rig.start_game()
            rig.switch("s_target")
            rig.switch("s_tilt")
            rig.drain()
            expect(rig).not_to_have_posted("ball_save_default_saving_ball")
            expect(rig.player.ball).to_equal(2)
        finally:
            rig.stop()


def describe_other_ball_saves():
    @pytest.fixture
    def rig(tmp_path):
        rig = GameRig(basic_machine(tmp_path, edit=_edit(SAVES)))
        rig.start_game()
        rig.machine.ball_saves["default"].disable()    # so each spec sees only the save it enables
        yield rig
        rig.stop()

    def it_saves_two_balls_and_reads_mpfs_plus_seconds(rig):  # Futurama's pazuzu_ball_save
        rig.post("start_pazuzu")
        expect(_save(rig, "pazuzu").config.active_time).to_equal(50)
        rig.drain()
        rig.drain()
        expect(rig.player.ball).to_equal(1)
        expect(_save(rig, "pazuzu").enabled).to_be_false()

    def it_saves_any_number_with_balls_to_save_minus_one(rig):  # MPF: test_unlimited
        rig.post("start_unlimited")
        for _ in range(4):
            rig.drain()
        expect(rig.player.ball).to_equal(1)
        expect(_save(rig, "unlimited").enabled).to_be_true()

    def it_saves_only_the_last_ball_in_play(rig):  # MPF: test_only_last (Grand Prix's ball_start)
        rig.post("start_last_ball")
        rig.game.balls_in_play = 2                       # as in a multiball (this machine has one ball out)
        rig.machine.events.post_relay("ball_drain", balls=1)
        rig.advance()
        expect(rig).not_to_have_posted("ball_save_last_ball_saving_ball")
        expect(rig.game.balls_in_play).to_equal(1)
        rig.machine.events.post_relay("ball_drain", balls=1)
        rig.advance()
        expect(rig).to_have_posted("ball_save_last_ball_saving_ball", times=1)

    def it_can_be_enabled_from_a_mode(rig):
        rig.machine.ball_saves["pazuzu"].enable()
        expect(rig).to_have_posted("ball_save_pazuzu_enabled", times=1)


def describe_ball_save_config():
    def it_waits_before_serving_with_eject_delay(tmp_path):  # MPF: test_eject_delay
        rig = GameRig(basic_machine(tmp_path, edit=_edit({"slow": {"active_time": "10s", "eject_delay": "2s",
                                                                    "enable_events": "mode_base_started"}})))
        try:
            rig.start_game()
            rig.drain()
            expect(rig.machine.trough().balls).to_equal(3)
            rig.advance(2.5)
            expect(rig.machine.trough().balls).to_equal(2)
        finally:
            rig.stop()

    @pytest.mark.parametrize(("data", "message"), [
        ({"enable_events": "x", "timer_start_events": "x"}, "both enable_events and timer_start_events"),
        ({"ball_locks": "bd_lock"}, "not supported yet: ball_locks"),
        ({"active_tim": "10s"}, "unknown setting"),
        ({"active_time": "soon"}, "isn't a time"),
    ])
    def it_explains_a_mistake(data, message):
        with pytest.raises(ConfigError, match=message):
            BallSaveConfig.from_yaml("x", data)

    def it_reads_mpfs_ms_numbers():
        expect(BallSaveConfig.from_yaml("x", {"hurry_up_time": 2000, "grace_period": "2s"}).hurry_up_time).to_equal(2.0)
