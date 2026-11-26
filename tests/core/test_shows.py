"""Shows: YAML files in a mode's folder, played over the light stack."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.testing import GameRig, expect

RED, GREEN, WHITE, BLACK = (255, 0, 0), (0, 255, 0), (255, 255, 255), (0, 0, 0)

SHOWS = {
    # frames: one column per lane, a letter's color from colors:
    "modes/base/chase.yaml": """
        every: 0.1s
        lights: lanes
        colors: {R: ff0000}
        frames: |
          R..
          .R.
          ..R
    """,
    # '-' leaves a light alone; spaces only line columns up; a token for the color
    "modes/base/half.yaml": """
        every: 0.5s
        lights: [l_lane_1, lanes]
        colors: {X: (color)}
        frames: |
          X  X - X
    """,
    # MPF's steps: absolute and relative times, coils, events, a fade, a hold
    "modes/base/steps.yaml": """
        - time: 0
          lights: {lanes: on}
          events: steps_began
        - time: 0.5
          coils: c_left_sling
          lights: {l_lane_1: {color: 00ff00, fade: 200ms}}
        - time: +0.5s
          events: steps_held
          duration: -1
    """,
    # a token for the lights, too
    "modes/base/lit.yaml": """
        - duration: -1
          lights: {(lights): (color)}
    """,
    "modes/frenzy/frenzy_lanes.yaml": """
        - duration: -1
          lights: {lanes: ff0000}
    """,
}


def _machine(config):
    config["lights"] = {f"l_lane_{i}": {"number": str(10 + i)} for i in range(1, 4)} | config["lights"]
    config["light_groups"] = {"lanes": "l_lane_1, l_lane_2, l_lane_3"}


@pytest.fixture
def game(tmp_path):
    rig = GameRig(basic_machine(tmp_path, edit=_machine, files=SHOWS))
    rig.start_game()
    yield rig
    rig.stop()


def _lanes(game):
    return [game.machine.lights[f"l_lane_{i}"].current_color() for i in range(1, 4)]


def _base(game):
    return game.mode("base")


def describe_shows():
    def it_loads_every_yaml_file_in_a_mode_folder_as_a_show(game):
        loaded = sorted(name for name in game.machine.shows.shows if "." in name)
        expect(loaded).to_equal(["base.chase", "base.half", "base.lit", "base.steps", "frenzy.frenzy_lanes"])

    def describe_mpfs_built_in_shows():
        def it_flashes_a_group(game):
            _base(game).play_show("flash", show_tokens={"lights": "lanes"}, speed=2)
            expect(_lanes(game)).to_equal([WHITE, WHITE, WHITE])
            game.advance(0.6)
            expect(_lanes(game)).to_equal([BLACK, BLACK, BLACK])

        def it_holds_a_color(game):
            _base(game).play_show("led_color", show_tokens={"lights": "l_lane_2", "color": "00ff00"})
            game.advance(5)
            expect(_lanes(game)).to_equal([BLACK, GREEN, BLACK])

    def describe_frames():
        def it_plays_a_row_per_frame_across_the_groups_lights(game):
            _base(game).play_show("chase", loops=0)
            expect(_lanes(game)).to_equal([RED, BLACK, BLACK])
            game.advance(0.1)
            expect(_lanes(game)).to_equal([BLACK, RED, BLACK])
            game.advance(0.1)
            expect(_lanes(game)).to_equal([BLACK, BLACK, RED])

        def it_leaves_dash_lights_alone_and_takes_a_token_for_a_color(game):
            game.machine.lights["l_lane_2"].color("00ff00")
            _base(game).play_show("half", show_tokens={"color": "ffffff"})
            expect(_lanes(game)).to_equal([WHITE, GREEN, WHITE])  # l_lane_1 twice: columns can repeat

        def it_loops_forever_by_default(game):
            _base(game).play_show("chase")
            game.advance(0.35)  # three frames of 0.1 s, then back to the first
            expect(_lanes(game)).to_equal([RED, BLACK, BLACK])

    def describe_steps():
        def it_follows_mpfs_timing_and_runs_coils_and_events(game):
            _base(game).play_show("steps", loops=0)
            expect(_lanes(game)).to_equal([WHITE, WHITE, WHITE])
            expect(game).to_have_posted("steps_began", times=1)
            game.advance(0.5)
            expect(game.machine.coils["c_left_sling"].pulses).to_equal(1)
            game.advance(0.1)
            red, green, _ = game.machine.lights["l_lane_1"].current_color()  # halfway through fading to green
            expect(red).to_be_close_to(128, within=1)
            expect(green).to_equal(255)
            game.advance(0.4)
            expect(game).to_have_posted("steps_held", times=1)
            game.advance(10)  # duration -1: it holds
            expect(game.machine.lights["l_lane_2"].current_color()).to_equal(WHITE)

        def it_takes_tokens_in_names_too(game):
            _base(game).play_show("lit", show_tokens={"lights": "l_lane_3", "color": "00ff00"})
            expect(_lanes(game)).to_equal([BLACK, BLACK, GREEN])

    def describe_the_light_stack():
        def it_covers_lights_and_gives_them_back_when_it_stops(game):
            game.machine.lights["l_lane_2"].color("00ff00")      # set by the game, priority 0
            running = _base(game).play_show("chase", loops=0)
            game.advance(0.1)
            expect(_lanes(game)[1]).to_equal(RED)
            running.stop()
            expect(_lanes(game)).to_equal([BLACK, GREEN, BLACK])

        def it_stops_a_modes_shows_when_the_mode_stops(game):
            game.post("frenzy_lit")
            game.mode("frenzy").play_show("frenzy_lanes")
            expect(_lanes(game)).to_equal([RED, RED, RED])
            game.advance(10)  # Frenzy ends after 10 seconds
            expect(game.mode("frenzy")).to_be_stopped()
            expect(_lanes(game)).to_equal([BLACK, BLACK, BLACK])

        def it_lets_a_higher_priority_show_cover_a_lower_one(game):
            _base(game).play_show("lit", key="under", show_tokens={"lights": "lanes", "color": "00ff00"})
            on_top = _base(game).play_show("lit", key="over", priority=10,
                                           show_tokens={"lights": "l_lane_1", "color": "ff0000"})
            expect(_lanes(game)).to_equal([RED, GREEN, GREEN])
            on_top.stop()
            expect(_lanes(game)).to_equal([GREEN, GREEN, GREEN])

    def describe_playing():
        def it_plays_another_modes_show_by_its_full_name(game):
            _base(game).play_show("frenzy.frenzy_lanes")
            expect(_lanes(game)).to_equal([RED, RED, RED])

        def it_explains_a_show_it_cant_find(game):
            with pytest.raises(ConfigError, match="No show named 'nope'"):
                _base(game).play_show("nope")

        def it_replaces_a_show_playing_under_the_same_key(game):
            first = _base(game).play_show("chase")
            _base(game).play_show("chase")
            expect(first.stopped).to_be_true()
            expect(len(game.machine.shows.playing)).to_equal(1)

        def it_stops_a_show_by_name(game):
            _base(game).play_show("chase")
            _base(game).stop_show("chase")
            expect(game.machine.shows.playing).to_equal({})
            expect(_lanes(game)).to_equal([BLACK, BLACK, BLACK])

        def it_plays_faster_at_a_higher_speed(game):
            _base(game).play_show("chase", loops=0, speed=2)
            game.advance(0.05)
            expect(_lanes(game)).to_equal([BLACK, RED, BLACK])

        def it_starts_at_a_step(game):
            _base(game).play_show("chase", start_step=3)
            expect(_lanes(game)).to_equal([BLACK, BLACK, RED])

        def it_loops_as_many_times_as_asked_then_completes(game):
            _base(game).play_show("chase", loops=1, events_when_played=("chase_played",),
                                  events_when_looped=("chase_looped",), events_when_completed=("chase_done",),
                                  events_when_stopped=("chase_stopped",))
            game.advance(0.65)  # two passes of three 0.1 s frames
            expect(game).to_have_posted("chase_played", times=1)
            expect(game).to_have_posted("chase_looped", times=1)
            expect(game).to_have_posted("chase_done", times=1)
            expect(game).to_have_posted("chase_stopped", times=1)
            expect(game.machine.shows.playing).to_equal({})

        def it_pauses_resumes_and_advances(game):
            running = _base(game).play_show("chase")
            running.pause()
            game.advance(1)
            expect(_lanes(game)).to_equal([RED, BLACK, BLACK])
            running.advance()
            expect(_lanes(game)).to_equal([BLACK, RED, BLACK])
            running.resume()
            expect(_lanes(game)).to_equal([BLACK, BLACK, RED])

        def it_refuses_a_token_the_show_doesnt_have(game):
            with pytest.raises(ConfigError, match="no token named colour"):
                _base(game).play_show("half", show_tokens={"colour": "ffffff"})


def describe_show_files():
    @pytest.mark.parametrize(("text", "message"), [
        ("every: 0.1s\nlights: lanes\nframes: |\n  R..\n", "'R' has no color"),
        ("every: 0.1s\nlights: lanes\ncolors: {R: ff0000}\nframes: |\n  R.\n", "has 2 columns, but its lights are 3"),
        ("every: 0.1s\nlights: lanes\nframes: |\n  ...\nspeed: 2\n", "not speed"),
        ("every: 0.1s\nlights: l_nope\nframes: |\n  .\n", "No light or light group named 'l_nope'"),
        ("- duration: 1\n  sounds: boom\n", "sounds in shows isn't supported yet"),
        ("- duration: 1\n  coils: c_nope\n", "no coil named 'c_nope'"),
        ("- duration: soon\n", "isn't a time"),
        ("- duration: 1\n  coils: {c_left_sling: {action: hold}}\n", "action is pulse, enable or disable"),
    ])
    def it_explains_a_show_it_cant_load(tmp_path, text, message):
        folder = basic_machine(tmp_path, edit=_machine, files={"modes/base/broken.yaml": text})
        with pytest.raises(ConfigError, match=message):
            GameRig(folder)
