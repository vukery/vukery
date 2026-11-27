"""vuk me's keyboard (MPF's keyboard: section): keys press switches and post events."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.dashboard.keys import MOD_CTRL, MOD_SHIFT, KeyboardInput, key_name
from vukery.media.keyboard import load
from vukery.testing import GameRig, expect

KEYBOARD = {
    "z": {"switch": "s_left_flipper"},
    1: {"switch": "s_trough1", "toggle": True},     # YAML reads 1: as a number
    "t": {"switch": "s_target", "invert": True},
    "Ctrl+L": {"event": "light_all", "params": {"color": "ffffff"}},
    "debug": True,                                  # MPF's section-wide setting
}
Z, ONE, T, L = ord("z"), ord("1"), ord("t"), ord("l")


@pytest.fixture
def game(tmp_path):
    def edit(config):
        config["keyboard"] = KEYBOARD

    rig = GameRig(basic_machine(tmp_path, edit=edit), dashboard=True)
    sent = []

    def send(message):
        sent.append(message)
        rig.machine.media.handle(message, from_dashboard=True)

    rig.keys = KeyboardInput(rig.dashboard, send)
    rig.sent = sent
    yield rig
    rig.stop()


def _on(game, switch):
    game.advance(0.1)
    return game.machine.switches[switch].state == 1


def describe_keys():
    def it_holds_a_switch_while_its_key_is_held(game):
        game.keys.press(Z, "z")
        expect(_on(game, "s_left_flipper")).to_be_true()
        game.keys.release(Z)
        expect(_on(game, "s_left_flipper")).to_be_false()

    def it_flips_a_toggle_switch_on_each_press(game):
        expect(_on(game, "s_trough1")).to_be_true()     # a ball is home
        game.keys.press(ONE, "1")
        game.keys.release(ONE)
        expect(_on(game, "s_trough1")).to_be_false()
        game.keys.press(ONE, "1")
        expect(_on(game, "s_trough1")).to_be_true()

    def it_holds_an_inverted_switch_until_its_key_is_pressed(game):
        game.keys.sync()
        expect(_on(game, "s_target")).to_be_true()
        game.keys.press(T, "t")
        expect(_on(game, "s_target")).to_be_false()
        game.keys.release(T)
        expect(_on(game, "s_target")).to_be_true()

    def it_posts_an_event_with_its_params(game):
        game.keys.press(L, "ctrl+l")
        game.advance()
        expect([kwargs for name, kwargs in game.posted if name == "light_all"]).to_equal([{"color": "ffffff"}])

    def it_ignores_a_key_repeating_while_held(game):
        game.keys.press(L, "ctrl+l")
        game.keys.press(L, "ctrl+l")
        game.advance()
        expect(game).to_have_posted("light_all", times=1)

    def it_releases_what_a_key_pressed_even_after_ctrl_is_let_go(game):
        game.keys.press(Z, "z")
        game.keys.release(Z)
        game.keys.press(L, "ctrl+l")
        game.keys.release(L)                          # released as plain "l": still the same key
        expect(game.keys.held).to_equal({})

    def it_ignores_keys_it_doesnt_know(game):
        game.keys.press(ord("q"), "q")
        game.keys.release(ord("q"))
        expect(game.sent).to_equal([])

    def it_sends_nothing_on_real_hardware(game):
        game.dashboard.layout["switch_input"] = False
        game.keys.press(Z, "z")
        game.keys.press(L, "ctrl+l")
        expect(game.sent).to_equal([])

    def it_refuses_an_event_from_the_dashboard_on_real_hardware(game, monkeypatch):
        monkeypatch.setattr(game.machine, "platform_is_simulated", lambda: False)
        game.machine.media.handle({"type": "event", "name": "light_all"}, from_dashboard=True)
        game.advance()
        expect(game).not_to_have_posted("light_all")

    def it_tells_the_dashboard_its_keys(game):
        expect(game.dashboard.layout["keyboard"]["ctrl+l"]).to_equal({"event": "light_all",
                                                                     "params": {"color": "ffffff"}})
        expect(game.dashboard.layout["keyboard"]["1"]).to_equal({"switch": "s_trough1", "toggle": True})


def describe_key_names():
    def it_names_a_key_press_as_the_config_does():
        expect(key_name(ord("z"), 0)).to_equal("z")
        expect(key_name(ord("/"), 0)).to_equal("/")
        expect(key_name(ord("l"), MOD_CTRL | MOD_SHIFT)).to_equal("ctrl+shift+l")
        expect(key_name(65293, 0, lambda _symbol: "RETURN")).to_equal("enter")
        expect(key_name(32, 0, lambda _symbol: "SPACE")).to_equal("space")
        expect(key_name(48, 0)).to_equal("0")

    @pytest.mark.parametrize(("entries", "message"), [
        ({"z": {"switch": "s_nope"}}, "no switch named 's_nope'"),
        ({"z": {"event": "x", "switch": "s_start"}}, "not both"),
        ({"z": {"toggle": True}}, "a switch or an event"),
        ({"z": {"switch": "s_start", "mc_event": "x"}}, "not supported: mc_event"),
        ({"hyper+z": {"switch": "s_start"}}, "isn't a modifier"),
        ({"ctrl+z": {"switch": "s_start"}, "Ctrl+Z": {"event": "x"}}, "the same key"),
    ])
    def it_explains_a_mistake(entries, message):
        with pytest.raises(ConfigError, match=message):
            load(entries, {"s_start"})

    def it_reads_mpfs_key_names():
        keys = load({"slash": {"switch": "s_start"}, "shift+Ctrl+A": {"event": "x"}, "spacebar": {"event": "y"}},
                    {"s_start"})
        expect(sorted(keys)).to_equal(["/", "ctrl+shift+a", "space"])
