"""The vuk me dashboard: what the engine tells it, what it may send back, and where things go."""

from pathlib import Path

import pytest
import yaml

from vukery.core.errors import ConfigError
from vukery.dashboard import layout as lay
from vukery.dashboard.state import DashboardState
from vukery.media.arrangement import Arrangement, write_config
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
        expect(layout["positions"]["playfield"]["l_frenzy"]).to_equal([0.5, 0.54])
        expect(layout["positions"]["backbox"]).to_equal({})
        expect(layout["modes"]).to_equal(["attract", "game", "base", "frenzy"])
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
        config = DashboardConfig.from_yaml({"playfield": {"s_target": [0.5, 1]}, "backbox": {"l_x": [0, 0]}})
        expect(config.positions).to_equal({"backbox": {"l_x": (0.0, 0.0)}, "playfield": {"s_target": (0.5, 1.0)}})

    def it_rejects_positions_off_the_pane():
        with pytest.raises(ConfigError, match="from 0 to 1"):
            DashboardConfig.from_yaml({"playfield": {"s_target": [1.5, 0.5]}})

    def it_rejects_a_switch_in_two_places():
        with pytest.raises(ConfigError, match="not both"):
            DashboardConfig.from_yaml({"playfield": {"s_target": [0.5, 0.5]}, "backbox": {"s_target": [0.5, 0.5]}})

    def it_rejects_names_that_arent_switches_or_lights(tmp_path):
        import shutil

        game = tmp_path / "game"
        shutil.copytree(EXAMPLES / "basic", game)
        config = game / "config" / "dashboard.yaml"
        config.write_text(config.read_text().replace("s_target: [0.5, 0.62]", "s_targte: [0.5, 0.62]"))
        with pytest.raises(ConfigError, match="no switch or light named s_targte"):
            GameRig(game)

    def it_needs_a_true_or_false_lock():
        with pytest.raises(ConfigError, match="arrangement_lock"):
            DashboardConfig.from_yaml({"arrangement_lock": "yes"})


def describe_the_layout():
    def it_has_a_full_height_list_the_backbox_over_the_displays_and_the_playfield():
        panes = lay.panes(1000, 800, Arrangement.default(["main", "apron"]))
        expect(round(panes["list"].w)).to_equal(392)                          # 40%, less the margins
        expect(round(panes["list"].h)).to_equal(792)                          # full height
        expect(panes["main"].x).to_equal(panes["backbox"].x)
        expect(panes["backbox"].y > panes["main"].y > panes["apron"].y).to_equal(True)
        expect(panes["playfield"].x > panes["backbox"].x > panes["list"].x).to_equal(True)

    def it_fits_a_display_in_its_pane_keeping_its_shape():
        screen = lay.fit(lay.Rect(0, 0, 400, 400), 1920, 720)
        expect((screen.w, round(screen.h), round(screen.y))).to_equal((400.0, 150, 125))

    def it_lists_the_game_then_switches_lights_coils_and_devices(rig):
        rows, _ = lay.list_rows(rig.dashboard.layout)
        expect([r.name for r in rows if r.kind == "title"]).to_equal(["Game", "Switches", "Lights", "Coils", "Devices"])

    def it_gives_every_row_a_fixed_height_so_text_never_shrinks(rig):
        rows, total = lay.list_rows(rig.dashboard.layout)
        expect({r.height for r in rows if r.kind in ("switch", "light", "coil")}).to_equal({lay.ROW})
        expect(total > 0).to_equal(True)

    def describe_the_scrollbar():
        def it_fills_the_track_when_everything_fits():
            track = lay.Rect(0, 0, 10, 300)
            expect(lay.thumb(track, 200, 300, 0)).to_equal(track)

        def it_moves_down_as_the_list_scrolls():
            track = lay.Rect(0, 0, 10, 300)
            top = lay.thumb(track, 900, 300, 0)
            bottom = lay.thumb(track, 900, 300, 600)
            expect((round(top.h), round(top.y), round(bottom.y))).to_equal((100, 200, 0))


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


def describe_the_arrangement():
    def it_defaults_to_the_list_at_40_percent():
        panes = Arrangement.default(["dmd"]).to_panes()
        expect(list(panes)).to_equal(["list", "backbox", "dmd", "playfield"])
        expect(panes["list"]).to_equal({"width": 40.0, "height": 100.0})
        expect(round(panes["list"]["width"] + panes["backbox"]["width"] + panes["playfield"]["width"], 1)).to_equal(
            100.0)
        expect(round(panes["backbox"]["height"] + panes["dmd"]["height"], 1)).to_equal(100.0)

    def it_reads_back_what_it_writes():
        arrangement = Arrangement(x1=35.0, x2=70.5, stack=(("backbox", 60.0), ("main", 25.0), ("apron", 15.0)))
        expect(Arrangement.from_panes(arrangement.to_panes(), ["main", "apron"])).to_equal(arrangement)

    def it_rejects_panes_that_dont_fit_together():
        panes = Arrangement.default(["dmd"]).to_panes()
        panes["dmd"]["width"] = 20.0  # the backbox is 35% wide, and the dmd shares its column
        with pytest.raises(ConfigError, match="dmd"):
            Arrangement.from_panes(panes, ["dmd"])

    def it_rejects_unknown_panes():
        with pytest.raises(ConfigError, match="no pane named switches"):
            Arrangement.from_panes({"switches": {"width": 10, "height": 10}})

    def describe_dragging_an_edge():
        def it_rounds_to_a_tenth_of_a_percent():
            expect(Arrangement().drag("x2", 66.6666).x2).to_equal(66.7)

        def it_keeps_every_pane_at_least_five_percent():
            expect(Arrangement().drag("x2", 99.0).x2).to_equal(95.0)
            expect(Arrangement().drag("x1", 0.0).x1).to_equal(5.0)

        def it_moves_the_edge_between_the_backbox_and_a_display():
            moved = Arrangement.default(["dmd"]).drag("y1", 70.0)
            expect(moved.stack).to_equal((("backbox", 70.0), ("dmd", 30.0)))


def describe_config_dashboard_yaml():
    def it_saves_every_pane_and_place(tmp_path):
        path = tmp_path / "dashboard.yaml"
        path.write_text("dashboard:\n  arrangement_lock: false\n")
        positions = {"backbox": {"l_frenzy": [0.25, 0.5]}, "playfield": {"s_target": [0.5, 0.62]}}
        write_config(path, Arrangement().drag("x2", 66.66), positions)
        config = DashboardConfig.from_yaml(yaml.safe_load(path.read_text())["dashboard"])
        expect(config.arrangement.x2).to_equal(66.7)
        expect(config.positions["backbox"]).to_equal({"l_frenzy": (0.25, 0.5)})
        expect("playfield: {width: 33.3, height: 100.0}" in path.read_text()).to_equal(True)

    def it_is_where_the_examples_keep_their_dashboard(rig):
        expect(rig.dashboard.layout["config_file"].endswith("examples/basic/config/dashboard.yaml")).to_equal(True)
        expect(rig.dashboard.layout["panes"]).to_equal(Arrangement().to_panes())
        expect(rig.dashboard.layout["arrangement_lock"]).to_equal(False)


class _Window:  # what the view needs from a pyglet window, for specs
    width, height = 1000, 800


def describe_the_dashboard_window():
    def _view(tmp_path, lock=False, positions=None):
        from vukery.dashboard.app import DashboardView

        clock = {"now": 0.0}
        sent = []
        state = DashboardState()
        state.apply({"type": "welcome", "displays": {}, "slides": {}, "showing": {}, "players": {}, "state": {},
                     "dashboard": {"panes": Arrangement().to_panes(), "arrangement_lock": lock,
                                   "config_file": str(tmp_path / "dashboard.yaml"), "switch_input": True,
                                   "switches": [{"name": "s_target", "tags": []}],
                                   "lights": [{"name": "l_frenzy"}],
                                   "positions": positions or {"backbox": {}, "playfield": {}}}})
        view = DashboardView(_Window(), state, sent.append, now=lambda: clock["now"])
        return view, sent, clock

    def _row(view, name):
        rect = next(r for r, n, _ in view.list_hits if n == name)
        return rect.x + 40, rect.y + rect.h / 2

    def _saved(tmp_path):
        return yaml.safe_load((tmp_path / "dashboard.yaml").read_text())["dashboard"]

    def it_drags_an_edge_and_saves_on_release(tmp_path):
        view, _, _ = _view(tmp_path)
        view.press(750, 400)  # the edge between the middle column and the playfield (75%)
        view.drag_to(800, 400)
        view.release(800, 400)
        expect(_saved(tmp_path)["panes"]["playfield"]).to_equal({"width": 20.0, "height": 100.0})

    def it_taps_a_switch_on_a_quick_click(tmp_path):
        view, sent, clock = _view(tmp_path)
        view.press(*_row(view, "s_target"))
        view.release(*_row(view, "s_target"))
        clock["now"] = 0.1
        view.tick()
        expect([m["state"] for m in sent]).to_equal([1, 0])

    def it_holds_a_switch_while_the_button_is_down(tmp_path):
        view, sent, clock = _view(tmp_path)
        view.press(*_row(view, "s_target"))
        clock["now"] = 0.2
        view.tick()
        expect(sent).to_equal([{"type": "switch", "name": "s_target", "state": 1}])
        view.release(*_row(view, "s_target"))
        expect(sent[-1]["state"]).to_equal(0)

    def it_places_a_switch_dragged_onto_the_playfield(tmp_path):
        view, sent, _ = _view(tmp_path)
        field = view.area("playfield")
        view.press(*_row(view, "s_target"))
        view.drag_to(field.x + field.w / 2, field.y + field.h / 4)
        view.release(field.x + field.w / 2, field.y + field.h / 4)
        expect(sent).to_equal([])  # placing it never presses it
        expect(_saved(tmp_path)["playfield"]).to_equal({"s_target": [0.5, 0.25]})

    def it_moves_a_light_from_the_playfield_to_the_backbox(tmp_path):
        view, _, _ = _view(tmp_path, positions={"backbox": {}, "playfield": {"l_frenzy": [0.5, 0.5]}})
        field, box = view.area("playfield"), view.area("backbox")
        view.press(*field.at(0.5, 0.5))
        view.drag_to(*box.at(0.1, 0.9))
        view.release(*box.at(0.1, 0.9))
        saved = _saved(tmp_path)
        expect((saved.get("playfield"), saved["backbox"])).to_equal((None, {"l_frenzy": [0.1, 0.9]}))

    def it_takes_a_switch_off_when_dropped_on_the_list(tmp_path):
        view, _, _ = _view(tmp_path, positions={"backbox": {}, "playfield": {"s_target": [0.5, 0.5]}})
        view.press(*view.area("playfield").at(0.5, 0.5))
        view.drag_to(100, 400)
        view.release(100, 400)
        expect(_saved(tmp_path).get("playfield")).to_equal(None)

    def it_changes_nothing_when_the_arrangement_is_locked(tmp_path):
        view, _, _ = _view(tmp_path, lock=True)
        view.press(750, 400)
        view.drag_to(800, 400)
        view.release(800, 400)
        field = view.area("playfield")
        view.press(*_row(view, "s_target"))
        view.drag_to(*field.at(0.5, 0.5))
        view.release(*field.at(0.5, 0.5))
        expect(view.arrangement).to_equal(Arrangement())
        expect((tmp_path / "dashboard.yaml").exists()).to_equal(False)

    def it_keeps_the_playfield_1_to_2_and_the_backbox_square_however_the_panes_are_sized(tmp_path):
        view, _, _ = _view(tmp_path)
        for edge, percent in (("x2", 60.0), ("x1", 20.0), ("x2", 90.0)):
            view.drag_to(0, 0)  # (nothing grabbed)
            view.arrangement = view.arrangement.drag(edge, percent)
            view.layout_panes()
            field, box = view.area("playfield"), view.area("backbox")
            expect(round(field.h / field.w, 3)).to_equal(2.0)
            expect(round(box.h / box.w, 3)).to_equal(1.0)

    def it_scrolls_the_list_with_the_wheel_but_not_past_its_end(tmp_path):
        view, _, _ = _view(tmp_path)
        view.list_total = view.list_area.h + 100
        view.scroll_by(100, 400, -50)
        expect(view.scroll).to_equal(100.0)
        view.scroll_by(100, 400, 50)
        expect(view.scroll).to_equal(0.0)
