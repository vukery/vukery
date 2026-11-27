"""Ball search (MPF's): the scenarios follow MPF's test_BallSearch.py, with COMBAT's settings."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.devices.ball_search import PlayfieldConfig
from vukery.testing import GameRig, expect

PLAYFIELD = {"enable_ball_search": True, "ball_search_timeout": "15s", "ball_search_interval": "250ms",
             "ball_search_wait_after_iteration": "10s"}


def _machine(tmp_path, playfield=None, edit=None):
    def change(config):
        config["switches"]["s_target"]["tags"] = "playfield_active"
        config["playfields"] = {"playfield": PLAYFIELD | (playfield or {})}
        if edit:
            edit(config)
    return GameRig(basic_machine(tmp_path, edit=change))


@pytest.fixture
def game(tmp_path):
    rig = _machine(tmp_path)
    rig.start_game()
    rig.switch("s_target")      # the ball's in play: the quiet timer counts from here
    yield rig
    rig.stop()


def _pulses(game, *coils):
    return [game.machine.coils[c].pulses for c in coils]


def _search(game):
    return game.machine.ball_search


def describe_ball_search():
    def it_waits_for_the_playfield_to_go_quiet(game):  # MPF: test_game_with_switches
        game.advance(14)
        game.switch("s_target")                                  # the ball's moving: start over
        game.advance(14)
        expect(_search(game).started).to_be_false()
        game.advance(1.1)
        expect(_search(game).started).to_be_true()
        expect(game).to_have_posted("ball_search_started", times=1)

    def it_fires_each_device_in_order_with_a_pause_between(game):
        game.advance(15.1)
        expect(_pulses(game, "c_left_sling", "c_right_sling")).to_equal([1, 0])
        game.advance(0.25)
        expect(_pulses(game, "c_left_sling", "c_right_sling")).to_equal([1, 1])
        expect(_pulses(game, "c_trough_eject")).to_equal([1])     # only the ball's serve: phase 1 skips a full trough

    def it_stops_when_the_ball_moves(game):
        game.advance(15.1)
        game.switch("s_target")
        expect(_search(game).started).to_be_false()
        expect(game).to_have_posted("ball_search_stopped", times=1)

    def it_ignores_the_hit_from_its_own_slingshot_pulse(game):
        game.advance(15.1)                                        # left sling pulsed just now
        game.switch("s_left_sling")
        expect(_search(game).started).to_be_true()
        game.advance(1)                                           # (round two pulsed it again at 15.5 s)
        game.switch("s_left_sling")                               # later: the ball
        expect(_search(game).started).to_be_false()

    def it_goes_through_three_phases_then_gives_up_with_a_new_ball(game):  # MPF: test_ball_search_iterations...
        game.advance(125)                                         # ten rounds, ten seconds apart
        for phase in (1, 2, 3):
            expect(game).to_have_posted(f"ball_search_phase_{phase}")
        expect(game).to_have_posted("ball_search_failed", times=1)
        expect(_search(game).lost_balls).to_equal(1)
        expect(game.machine.trough().balls).to_equal(1)          # a replacement was served
        expect(game.player.ball).to_equal(1)                      # the same ball goes on

    def it_counts_a_lost_ball_that_turns_up_as_found_not_drained(game):
        game.advance(125)                                         # given up: a replacement's out
        expect(_search(game).lost_balls).to_equal(1)
        game.drain()                                              # the lost ball drops into the trough
        expect(_search(game).lost_balls).to_equal(0)
        expect(game.player.ball).to_equal(1)

    def it_holds_a_game_start_while_searching(tmp_path):
        rig = _machine(tmp_path)
        try:
            rig.machine.ball_search.started = True                # as if searching between games
            rig.switch("s_start")
            expect(rig.game).to_be_none()
            expect(rig).to_have_posted("ball_search_prevents_game_start", times=1)
        finally:
            rig.stop()

    def it_gives_up_now_on_cancel_ball_search(game):  # MPF: test_ball_search_cancel_running
        game.advance(15.1)
        game.post("cancel_ball_search")
        expect(game).to_have_posted("ball_search_failed", times=1)

    def it_is_blocked_while_a_flipper_cradles_the_ball(game):  # MPF: test_prevent_ball_search_with_flipper_cradle
        game.post("flipper_cradle")
        game.advance(30)
        expect(_search(game).started).to_be_false()
        game.post("flipper_cradle_release")
        game.advance(15.1)
        expect(_search(game).started).to_be_true()

    def it_takes_a_games_own_device(game):  # COMBAT's kickers: plain coils, not ball devices
        fired = []
        game.machine.ball_search.register(1, lambda phase, iteration: fired.append(phase) or True, "kicker")
        game.advance(15.1)
        expect(fired).to_equal([1])

    def it_stays_off_unless_enabled(tmp_path):  # MPF: test_ball_search_does_not_start_when_disabled
        rig = _machine(tmp_path, {"enable_ball_search": False})
        try:
            rig.start_game()
            rig.advance(60)
            expect(rig).not_to_have_posted("ball_search_started")
        finally:
            rig.stop()


def describe_giving_up():
    @pytest.mark.parametrize(("action", "ends_game"), [("end_game", True), ("end_ball", False)])
    def it_does_the_failed_action(tmp_path, action, ends_game):  # MPF: test_give_up_with_end_ball / game_end
        rig = _machine(tmp_path, {"ball_search_failed_action": action})
        try:
            rig.start_game()
            rig.advance(125)
            if ends_game:
                expect(rig.game).to_be_none()
            else:
                expect(rig.player.ball).to_equal(2)
        finally:
            rig.stop()

    def it_ends_the_game_when_no_ball_is_left_to_serve(tmp_path):  # MPF: test_give_up_with_no_more_balls
        rig = _machine(tmp_path)
        try:
            rig.start_game()
            for name in ("s_trough1", "s_trough2", "s_trough3"):
                rig.machine.set_switch(name, 0)                    # every other ball is lost too
            rig.advance(125)
            expect(rig.game).to_be_none()
        finally:
            rig.stop()


def describe_a_plunger_lane():  # MPF: test_mechanical_eject
    def it_doesnt_search_while_the_ball_waits_to_be_plunged(tmp_path):
        def lane(config):
            config["switches"]["s_shooter_lane"] = {"number": "20"}
            config["ball_devices"]["bd_trough"]["eject_targets"] = "bd_shooter_lane"
            config["ball_devices"]["bd_shooter_lane"] = {"ball_switches": "s_shooter_lane", "mechanical_eject": True}

        rig = _machine(tmp_path, edit=lane)
        try:
            rig.start_game()
            rig.advance(60)
            expect(rig).not_to_have_posted("ball_search_started")
            rig.machine.set_switch("s_shooter_lane", 0)            # plunged
            rig.advance(15.1)
            expect(rig).to_have_posted("ball_search_started", times=1)
        finally:
            rig.stop()


def describe_playfield_config():
    @pytest.mark.parametrize(("section", "message"), [
        ({"upper": {}}, "only one playfield"),
        ({"playfield": {"ball_search_failed_action": "panic"}}, "new_ball, end_ball, end_game"),
        ({"playfield": {"ball_search_timeout": "soon"}}, "isn't a time"),
        ({"playfield": {"ball_search_bogus": 1}}, "not supported"),
    ])
    def it_explains_a_mistake(section, message):
        with pytest.raises(ConfigError, match=message):
            PlayfieldConfig.from_yaml(section)

    def it_reads_mpfs_defaults_and_units():
        config = PlayfieldConfig.from_yaml({"playfield": {"ball_search_interval": 250, "tags": "default"}})
        expect((config.enable_ball_search, config.ball_search_interval, config.ball_search_timeout,
                config.phase_searches)).to_equal((False, 0.25, 15.0, (3, 3, 4)))
