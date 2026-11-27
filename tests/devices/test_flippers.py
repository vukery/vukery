"""Flippers: the hardware rules each kind sets and clears (MPF's test_Flippers.py, at the platform's edge)."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.testing import GameRig, expect

COILS = {
    "c_flipper_main": {"number": "20", "default_pulse_ms": 10, "default_hold_power": 0.125},
    "c_flipper_hold": {"number": "21", "allow_enable": True},
}
SWITCHES = {"s_flipper": {"number": "30"}, "s_flipper_eos": {"number": "31"}}


def _machine(tmp_path, flipper):
    def edit(config):
        config["coils"] |= COILS
        config["switches"] |= SWITCHES
        config["flippers"] = {"f_test": {"main_coil": "c_flipper_main", "activation_switch": "s_flipper", **flipper}}

    return GameRig(basic_machine(tmp_path, edit=edit))


@pytest.fixture
def calls(monkeypatch):
    """Every rule call the flipper makes: (method, switches, coil, pulse ms, hold power, repulse)."""
    from vukery.platforms.simulated import SimulatedPlatform

    made = []

    def record(method):
        def call(self, *args):
            switches = tuple(a.hw_switch.number for a in args if hasattr(a, "hw_switch"))
            driver = next(a for a in args if hasattr(a, "hw_driver"))
            repulse = next(((r.enable_repulse, r.debounce_ms) for r in args[2:] if hasattr(r, "enable_repulse")), None)
            made.append((method, switches, driver.hw_driver.number, driver.pulse_settings.duration,
                         driver.hold_settings.power if driver.hold_settings else None, repulse))
        return call

    for method in ("set_pulse_on_hit_and_enable_and_release_rule", "set_pulse_on_hit_and_release_rule",
                   "set_pulse_on_hit_and_release_and_disable_rule",
                   "set_pulse_on_hit_and_enable_and_release_and_disable_rule", "clear_hw_rule"):
        monkeypatch.setattr(SimulatedPlatform, method, record(method))
    return made


def _flip(game, calls):
    game.machine.flippers["f_test"].enable()
    made = list(calls)
    calls.clear()
    game.machine.flippers["f_test"].disable()
    return made, sorted(calls)


def _switch(game, name):
    return game.machine.switches[name].hw.number


def _driver(game, name):
    return game.machine.coils[name].hw_driver.number


def describe_flippers():
    def it_pulses_and_holds_a_single_wound_flipper(tmp_path, calls):  # MPF: test_single
        game = _machine(tmp_path, {})
        try:
            enabled, cleared = _flip(game, calls)
            button = _switch(game, "s_flipper")
            expect(enabled).to_equal([("set_pulse_on_hit_and_enable_and_release_rule", (button,), _driver(game, "c_flipper_main"), 10, 0.125,
                                       None)])
            expect(cleared).to_equal([("clear_hw_rule", (button,), _driver(game, "c_flipper_main"), 10, 0.125, None)])
        finally:
            game.stop()

    def it_cuts_the_main_coil_at_eos_and_holds_with_the_hold_coil(tmp_path, calls):  # MPF: test_hold_with_eos
        game = _machine(tmp_path, {"hold_coil": "c_flipper_hold", "eos_switch": "s_flipper_eos", "use_eos": True})
        try:
            enabled, cleared = _flip(game, calls)
            button, eos = _switch(game, "s_flipper"), _switch(game, "s_flipper_eos")
            expect(enabled).to_equal([
                ("set_pulse_on_hit_and_release_and_disable_rule", (button, eos), _driver(game, "c_flipper_main"), 10, None, (False, 500)),
                ("set_pulse_on_hit_and_enable_and_release_rule", (button,), _driver(game, "c_flipper_hold"), 10, 1.0, None),
            ])
            expect(cleared).to_equal(sorted([("clear_hw_rule", (button,), _driver(game, "c_flipper_main"), 10, None, None),
                                             ("clear_hw_rule", (eos,), _driver(game, "c_flipper_main"), 10, None, None),
                                             ("clear_hw_rule", (button,), _driver(game, "c_flipper_hold"), 10, 1.0, None)]))
        finally:
            game.stop()

    def it_pulses_the_main_coil_of_a_dual_wound_flipper_without_eos(tmp_path, calls):
        game = _machine(tmp_path, {"hold_coil": "c_flipper_hold"})
        try:
            enabled, _ = _flip(game, calls)
            expect([(method, coil, hold) for method, _, coil, _, hold, _ in enabled]).to_equal([
                ("set_pulse_on_hit_and_release_rule", _driver(game, "c_flipper_main"), None),
                ("set_pulse_on_hit_and_enable_and_release_rule", _driver(game, "c_flipper_hold"), 1.0),
            ])
        finally:
            game.stop()

    def it_cuts_a_single_wound_flipper_to_hold_at_eos(tmp_path, calls):
        game = _machine(tmp_path, {"eos_switch": "s_flipper_eos", "use_eos": True, "repulse_on_eos_open": True,
                                   "eos_active_ms_before_repulse": "20ms"})
        try:
            enabled, _ = _flip(game, calls)
            expect(enabled).to_equal([("set_pulse_on_hit_and_enable_and_release_and_disable_rule",
                                       (_switch(game, "s_flipper"), _switch(game, "s_flipper_eos")), _driver(game, "c_flipper_main"), 10, 0.125,
                                       (True, 20))])
        finally:
            game.stop()

    def it_enables_with_the_ball_and_disables_as_it_ends(tmp_path):  # MPF's enable_events and disable_events
        game = _machine(tmp_path, {"hold_coil": "c_flipper_hold", "eos_switch": "s_flipper_eos", "use_eos": True})
        try:
            rules = game.machine.platform.rules
            expect(rules).to_equal({})
            game.start_game()
            expect(sorted(rules.values())).to_contain("pulse_on_hit_and_release_and_disable")
            game.drain()
            game.advance()
            expect(game.machine.flippers["f_test"].enabled).to_be_true()   # the next ball has started
        finally:
            game.stop()

    def it_shows_vuk_me_which_coils_its_rules_hold_on(tmp_path):
        game = _machine(tmp_path, {"hold_coil": "c_flipper_hold", "eos_switch": "s_flipper_eos", "use_eos": True})
        try:
            flipper = game.machine.flippers["f_test"]
            game.start_game()
            game.machine.set_switch("s_flipper", 1)                     # the button, held
            game.advance()
            expect(flipper.driven()).to_equal({"c_flipper_main", "c_flipper_hold"})
            game.machine.set_switch("s_flipper_eos", 1)                 # the flipper's up: main coil cut
            game.advance()
            expect(flipper.driven()).to_equal({"c_flipper_hold"})
            game.machine.set_switch("s_flipper", 0)
            game.advance()
            expect(flipper.driven()).to_equal(set())
        finally:
            game.stop()

    @pytest.mark.parametrize(("flipper", "message"), [
        ({"use_eos": True}, "use_eos needs an eos_switch"),
        ({"hold_coil": "c_left_sling"}, "can't be held on"),
        ({"main_coil_overwrite": {"pulse_ms": 20}}, "not supported yet: main_coil_overwrite"),
    ])
    def it_explains_a_mistake(tmp_path, flipper, message):
        with pytest.raises(ConfigError, match=message):
            _machine(tmp_path, flipper)
