"""The media protocol: what a media controller knows, and the engine's socket server."""

import asyncio
from pathlib import Path

import pytest

from vukery.core.clock import RealClock
from vukery.core.errors import ConfigError
from vukery.core.machine import Machine
from vukery.mc.state import MediaState
from vukery.media import protocol
from vukery.media.scenes import Scene, Text, build, scene
from vukery.testing import expect

EXAMPLE = Path(__file__).parents[2] / "examples" / "display"


def welcome(scene=None, **overrides):
    shown = scene or Scene(Text("{player.score:,}"), Text("BALL {player.ball}"), Text("{player.missing}"))
    message = {"type": "welcome", "displays": {"main": {"width": 800, "height": 480}},
               "scenes": {"score": shown.to_data()}, "showing": {"main": "score"},
               "player": 1, "players": {"1": {"score": 12340, "ball": 2}}}
    return {**message, **overrides}


class Clock:  # a media controller's clock, moved by hand
    def __init__(self):
        self.time = 0.0

    def __call__(self):
        return self.time


def _texts(state, display="main"):
    return [(t.text, round(t.x, 3), round(t.y, 3)) for t in state.texts(display)]


def describe_media_state():
    def it_fills_in_live_values():
        state = MediaState()
        state.apply(welcome())
        expect([t.text for t in state.texts("main")]).to_equal(["12,340", "BALL 2", ""])

    def it_follows_player_changes_and_turns():
        state = MediaState()
        state.apply(welcome())
        state.apply({"type": "player", "number": 2, "vars": {"score": 50, "ball": 1}})
        state.apply({"type": "turn", "number": 2})
        expect([t.text for t in state.texts("main")][:2]).to_equal(["50", "BALL 1"])

    def it_shows_nothing_for_an_unknown_or_empty_scene():
        state = MediaState()
        state.apply(welcome())
        state.apply({"type": "show", "display": "main", "scene": None})
        expect(state.texts("main")).to_equal([])

    def it_ignores_messages_it_doesnt_know():  # so the protocol can grow
        state = MediaState()
        state.apply(welcome())
        state.apply({"type": "something_new", "x": 1})
        expect(state.connected).to_be_true()

    def it_notices_the_engine_stopping():
        state = MediaState()
        state.apply({"type": "bye"})
        expect(state.engine_stopped).to_be_true()


def describe_scenes():
    def it_places_a_nested_scene_inside_its_parent():
        inner = Scene(Text("in", x=0.0, y=1.0, size=0.5), background="202060")
        state = MediaState()
        state.apply(welcome(Scene(inner.placed(x=0.75, y=0.25, width=0.5, height=0.5))))
        rect, text = state.draws("main")
        expect((rect.x, rect.y, rect.width, rect.height, rect.color)).to_equal((0.5, 0.0, 0.5, 0.5, "202060"))
        expect((text.x, text.y, text.size)).to_equal((0.5, 0.5, 0.25))  # the inner scene's top-left corner

    def it_slides_an_actor_in_when_the_scene_appears():
        clock = Clock()
        state = MediaState(now=clock)
        state.apply(welcome(Scene(Text("A"))))
        state.scenes["jackpot"] = Scene(Text("JACKPOT").enters("left", seconds=1)).to_data()
        state.apply({"type": "show", "display": "main", "scene": "jackpot"})
        expect(_texts(state)).to_equal([("JACKPOT", -0.5, 0.5)])   # a display to the left
        clock.time = 0.5
        expect(_texts(state)).to_equal([("JACKPOT", 0.25, 0.5)])   # eased: most of the way already
        clock.time = 1.0
        expect(_texts(state)).to_equal([("JACKPOT", 0.5, 0.5)])

    def it_slides_an_actor_out_over_the_next_scene_when_its_scene_goes():
        clock = Clock()
        state = MediaState(now=clock)
        state.apply(welcome(Scene(Text("BYE").exits("top", seconds=1), Text("STAYS"))))
        state.scenes["next"] = Scene(Text("NEXT")).to_data()
        state.apply({"type": "show", "display": "main", "scene": "next"})
        expect(_texts(state)).to_equal([("NEXT", 0.5, 0.5), ("BYE", 0.5, 0.5)])  # "STAYS" has no exit: gone
        clock.time = 0.5
        expect(_texts(state)).to_equal([("NEXT", 0.5, 0.5), ("BYE", 0.5, 0.75)])
        clock.time = 1.0
        expect(_texts(state)).to_equal([("NEXT", 0.5, 0.5)])
        expect(state.leaving).to_equal({})

    def it_moves_a_whole_nested_scene_with_its_exit():
        clock = Clock()
        state = MediaState(now=clock)
        group = Scene(Text("IN A GROUP")).placed(width=0.5, height=0.5).exits("right", seconds=1)
        state.apply(welcome(Scene(group)))
        state.scenes["next"] = Scene().to_data()
        state.apply({"type": "show", "display": "main", "scene": "next"})
        clock.time = 0.5
        expect(_texts(state)).to_equal([("IN A GROUP", 0.75, 0.5)])

    def it_doesnt_replay_an_entrance_for_a_scene_already_showing_when_it_connects():
        state = MediaState()
        state.apply(welcome(Scene(Text("HERE").enters("left"))))
        expect(_texts(state)).to_equal([("HERE", 0.5, 0.5)])


def describe_scene_functions():
    def it_names_a_scene_after_its_function():
        @scene
        def jackpot():
            return Scene(Text("JACKPOT"))

        expect(jackpot.scene_name).to_equal("jackpot")
        expect(build(jackpot).actors[0].text).to_equal("JACKPOT")

    def it_needs_a_scene_function_to_return_a_scene():
        @scene
        def broken():
            return Text("not a scene")

        with pytest.raises(ConfigError, match="returned .*, not a Scene"):
            build(broken)

    def it_only_holds_actors():
        with pytest.raises(ConfigError, match="holds actors"):
            Scene("JACKPOT")

    @pytest.mark.parametrize(("make", "message"), [
        (lambda: Text("A").enters("up"), "not 'up'"),
        (lambda: Text("A").exits("left", seconds=0), "takes some time"),
        (lambda: Text("A", anchor="middle"), "left, center or right"),
        (lambda: Scene(background="purple"), "Not a color"),
        (lambda: Scene().placed(width=0), "width and height above 0"),
    ])
    def it_explains_a_mistake(make, message):
        with pytest.raises(ConfigError, match=message):
            make()


def describe_media_server():
    def it_welcomes_a_media_controller_over_the_socket():
        loop = asyncio.new_event_loop()
        machine = Machine.from_folder(EXAMPLE, env="development", clock=RealClock(loop))

        async def scenario():
            # a free port, so the test doesn't collide with a running game
            machine.media.port = 0
            await machine.start()
            port = machine.media._server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(protocol.encode({"type": "hello", "version": protocol.VERSION,
                                          "displays": ["main"], "audio": False}))
            first = protocol.decode(await reader.readline())
            writer.close()
            return first

        try:
            message = loop.run_until_complete(scenario())
            expect(message["type"]).to_equal("welcome")
            expect(message["showing"]).to_equal({"main": "start_screen"})
            expect(set(message["scenes"])).to_equal({"start_screen", "score"})
            expect(message["displays"]).to_equal({"main": {"width": 800, "height": 480}})
        finally:
            machine.stop("test")
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(asyncio.sleep(0))
            loop.close()


def describe_scene_mistakes():
    def _display_machine(tmp_path, base_mode):
        from tests.helpers import basic_machine

        return basic_machine(tmp_path, example="display", files={"modes/base/mode.py": base_mode})

    def it_refuses_a_scene_defined_twice(tmp_path):
        from vukery.testing import GameRig

        folder = _display_machine(tmp_path, """
            from vukery import Mode
            from vukery.media.scenes import Scene, scene


            @scene
            def start_screen():   # the start_screen mode already has one
                return Scene()


            class Base(Mode):
                start_on = "ball_started"
                scenes = (start_screen,)
        """)
        with pytest.raises(ConfigError, match="'start_screen' is defined twice"):
            GameRig(folder)

    def it_explains_showing_a_scene_that_doesnt_exist_or_on_a_display_that_doesnt(tmp_path):
        from vukery.testing import GameRig

        folder = _display_machine(tmp_path, """
            from vukery import Mode


            class Base(Mode):
                start_on = "ball_started"
        """)
        rig = GameRig(folder)
        try:
            base = rig.mode("base")
            with pytest.raises(ConfigError, match="'missing', which isn't defined"):
                base.show_scene("missing")
            with pytest.raises(ConfigError, match="on display 'apron', which isn't in displays"):
                base.show_scene("start_screen", display="apron")
            with pytest.raises(ConfigError, match="Not a scene"):
                base.show_scene(42)
        finally:
            rig.stop()

    def it_refuses_a_media_controller_speaking_another_protocol_version():
        loop = asyncio.new_event_loop()
        machine = Machine.from_folder(EXAMPLE, env="development", clock=RealClock(loop))

        async def scenario():
            machine.media.port = 0
            await machine.start()
            port = machine.media._server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(protocol.encode({"type": "hello", "version": 99, "displays": ["main"], "audio": False}))
            answer = await reader.readline()
            writer.close()
            return answer

        try:
            expect(loop.run_until_complete(scenario())).to_equal(b"")  # the engine hung up
        finally:
            machine.stop()
            loop.run_until_complete(asyncio.sleep(0.05))
            loop.close()
