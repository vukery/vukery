"""The vuk me dashboard: what the engine tells it, what it may send back, and where things go."""

from pathlib import Path

import pytest

from vukery.core.errors import ConfigError
from vukery.dashboard import layout as lay
from vukery.dashboard.state import DashboardState
from vukery.media.dashboard import DashboardConfig
from vukery.testing import GameRig, expect

EXAMPLES = Path(__file__).parents[2] / "examples"


@pytest.fixture
def rig():
    game = GameRig(EXAMPLES / "basic", dashboard=True)
    yield game
    game.stop()


def _from_dashboard(rig, **message):
    rig.machine.media.handle(message, from_dashboard=True)
    rig.advance(0.1)


def describe_the_engine_side():
    def it_runs_a_media_server_for_a_game_without_displays(rig):
        expect(rig.machine.media is not None).to_equal(True)
        expect(rig.machine.media_controllers()).to_equal([])  # still no display windows

    def it_sends_the_machine_layout(rig):
        layout = rig.dashboard.layout
        expect([s["name"] for s in layout["switches"]][:2]).to_equal(["s_start", "s_trough1"])
        expect([c["name"] for c in layout["coils"]]).to_equal(
            ["c_trough_eject", "c_left_flipper", "c_right_flipper", "c_left_sling", "c_right_sling"])
        expect(layout["playfield"]).to_equal({"s_target": [0.5, 0.62], "l_frenzy": [0.5, 0.54]})
        expect(layout["switch_input"]).to_equal(True)

    def it_follows_switches(rig):
        rig.machine.set_switch("s_target", 1)
        rig.advance(0.1)
        expect(rig.dashboard.switch("s_target")).to_equal(True)

    def it_follows_lights(rig):
        rig.machine.lights["l_frenzy"].color("ff8800")
        rig.advance(0.1)
        expect(rig.dashboard.light("l_frenzy")).to_equal("ff8800")

    def it_shows_running_modes_highest_priority_first(rig):
        rig.start_game()
        rig.advance(0.1)
        expect(rig.dashboard.devices["modes"]).to_equal([["base", 100], ["game", 20]])

    def it_shows_balls_in_the_trough(rig):
        rig.advance(0.1)  # the next state update
        expect(rig.dashboard.device_lines()[0]).to_equal("bd_trough  3/3 balls")
        rig.start_game()
        rig.advance(0.1)
        expect(rig.dashboard.device_lines()[0]).to_equal("bd_trough  2/3 balls")

    def it_flashes_a_pulsed_coil(rig):
        rig.machine.coils["c_left_sling"].pulse()
        rig.advance(0.1)
        expect(rig.dashboard.coil_on("c_left_sling")).to_equal(True)
        rig.advance(1)
        expect(rig.dashboard.coil_on("c_left_sling")).to_equal(False)

    def it_shows_a_flipper_coil_on_while_its_button_is_held(rig):
        rig.start_game()
        rig.machine.set_switch("s_left_flipper", 1)
        rig.advance(0.1)
        expect(rig.dashboard.coil_on("c_left_flipper")).to_equal(True)
        expect(rig.dashboard.coil_on("c_right_flipper")).to_equal(False)


def describe_what_the_dashboard_can_send():
    def it_presses_switches(rig):
        _from_dashboard(rig, type="switch", name="s_start", state=1)
        _from_dashboard(rig, type="switch", name="s_start", state=0)
        expect(rig.game is not None).to_equal(True)

    def it_ignores_switches_from_a_plain_media_controller(rig):
        rig.machine.media.handle({"type": "switch", "name": "s_target", "state": 1}, from_dashboard=False)
        rig.advance(0.1)
        expect(rig.switches("s_target")).to_be_inactive()

    def it_ignores_switches_that_dont_exist(rig):
        _from_dashboard(rig, type="switch", name="s_nope", state=1)  # logged, not raised

    def it_ignores_switches_on_real_hardware(rig, monkeypatch):
        monkeypatch.setattr(rig.machine, "platform_is_simulated", lambda: False)
        _from_dashboard(rig, type="switch", name="s_target", state=1)
        expect(rig.switches("s_target")).to_be_inactive()

    def it_can_never_fire_a_coil(rig):
        rig.start_game()
        drivers = {name: list(coil.hw_driver.pulses) for name, coil in rig.machine.coils.items()}
        for message in ({"type": "pulse", "coil": "c_left_sling"}, {"type": "coil", "name": "c_left_sling"},
                        {"type": "enable", "name": "c_left_flipper"}, {"type": "switch", "name": "c_left_sling",
                                                                        "state": 1}):
            _from_dashboard(rig, **message)
        expect({name: list(c.hw_driver.pulses) for name, c in rig.machine.coils.items()}).to_equal(drivers)
        expect(rig.machine.coils["c_left_flipper"].enabled).to_equal(False)


def describe_the_dashboard_config():
    def it_takes_positions_from_zero_to_one():
        expect(DashboardConfig.from_yaml({"playfield": {"s_target": [0.5, 1]}}).playfield).to_equal(
            {"s_target": (0.5, 1.0)})

    def it_rejects_positions_off_the_playfield():
        with pytest.raises(ConfigError, match="from 0 to 1"):
            DashboardConfig.from_yaml({"playfield": {"s_target": [1.5, 0.5]}})

    def it_rejects_names_that_arent_switches_or_lights(tmp_path):
        import shutil

        game = tmp_path / "game"
        shutil.copytree(EXAMPLES / "basic", game)
        config = game / "config" / "machine.yaml"
        config.write_text(config.read_text().replace("s_target: [0.5, 0.62]", "s_targte: [0.5, 0.62]"))
        with pytest.raises(ConfigError, match="no switch or light named s_targte"):
            GameRig(game)


def describe_the_layout():
    def it_has_three_columns():
        panes = lay.panes(1920, 1080)
        expect(round(panes["backbox"].w)).to_equal(round(panes["backbox"].h))  # a square
        expect(round(panes["backbox"].y + panes["backbox"].h)).to_equal(1076)  # at the top
        expect(panes["game"].x).to_equal(panes["backbox"].x)                  # under it
        expect(round(panes["playfield"].h)).to_equal(1072)                     # full height
        expect(panes["playfield"].x > panes["backbox"].x > panes["lights"].x > panes["switches"].x).to_equal(True)
        expect(panes["coils"].x).to_equal(panes["switches"].x)  # 2×2 in the first column

    def it_lists_items_in_more_columns_when_they_dont_fit():
        cells = lay.cells(lay.Rect(0, 0, 400, 200), 30)
        expect(len({c.x for c in cells}) > 1).to_equal(True)
        expect(all(c.y >= 0 for c in cells)).to_equal(True)

    def it_stacks_displays_in_the_backbox_keeping_their_shape():
        rects = lay.displays(lay.Rect(0, 0, 500, 500), [("main", 800, 480), ("apron", 480, 272)])
        main, apron = rects["main"], rects["apron"]
        expect(round(main.w / main.h, 2)).to_equal(round(800 / 480, 2))
        expect(main.y > apron.y).to_equal(True)  # main on top

    def it_places_playfield_switches_and_leaves_cabinet_ones_off():
        game = GameRig(EXAMPLES / "basic", dashboard=True)
        try:
            spots = lay.playfield_spots(game.dashboard.layout)
        finally:
            game.stop()
        expect(spots["s_target"]).to_equal((0.5, 0.62))     # from dashboard: playfield:
        expect(spots["s_left_sling"][0] < 0.5 < spots["s_right_sling"][0]).to_equal(True)
        expect(spots["s_trough1"][1] < 0.1).to_equal(True)  # the trough sits at the bottom
        expect("s_start" in spots or "s_left_flipper" in spots).to_equal(False)


def describe_the_game_pane():
    def it_says_when_no_game_is_running():
        state = DashboardState()
        expect(state.game_lines()[0]).to_equal("No game in progress")

    def it_lists_players_and_modes(rig):
        rig.start_game(players=2)
        rig.switch("s_target")
        rig.advance(0.1)
        lines = rig.dashboard.game_lines()
        expect(lines[:3]).to_equal(["Player 1 of 2   Ball 1", "> P1  1,000", "  P2  0"])
        expect("  base  100" in lines).to_equal(True)
