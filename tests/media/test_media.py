"""The media protocol: what a media controller knows, and the engine's socket server."""

import asyncio
from pathlib import Path

import pytest

from vukery.core.clock import RealClock
from vukery.core.machine import Machine
from vukery.mc.state import MediaState
from vukery.media import protocol
from vukery.media.slides import Slide, Text
from vukery.testing import expect

EXAMPLE = Path(__file__).parents[2] / "examples" / "display"


def welcome(**overrides):
    slide = Slide(Text("{player.score:,}"), Text("BALL {player.ball}"), Text("{player.missing}"))
    message = {"type": "welcome", "displays": {"main": {"width": 800, "height": 480}},
               "slides": {"score": slide.to_data()}, "showing": {"main": "score"},
               "player": 1, "players": {"1": {"score": 12340, "ball": 2}}}
    return {**message, **overrides}


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

    def it_shows_nothing_for_an_unknown_or_empty_slide():
        state = MediaState()
        state.apply(welcome())
        state.apply({"type": "show", "display": "main", "slide": None})
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


def describe_slides():
    def it_rejects_bad_colors():
        with pytest.raises(Exception, match="Not a color"):
            Slide(background="purple")


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
            expect(set(message["slides"])).to_equal({"start_screen", "score"})
            expect(message["displays"]).to_equal({"main": {"width": 800, "height": 480}})
        finally:
            machine.stop("test")
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(asyncio.sleep(0))
            loop.close()


def describe_slide_mistakes():
    def _display_machine(tmp_path, base_mode):
        from tests.helpers import basic_machine

        return basic_machine(tmp_path, example="display", files={"modes/base/mode.py": base_mode})

    def it_refuses_a_slide_defined_twice(tmp_path):
        import pytest

        from vukery.core.errors import ConfigError
        from vukery.testing import GameRig

        folder = _display_machine(tmp_path, """
            from vukery import Mode
            from vukery.media.slides import Slide


            class Base(Mode):
                start_on = "ball_started"
                slides = {"start_screen": Slide()}   # start_screen already has one
        """)
        with pytest.raises(ConfigError, match="'start_screen' is defined twice"):
            GameRig(folder)

    def it_explains_showing_a_slide_that_doesnt_exist_or_on_a_display_that_doesnt(tmp_path):
        import pytest

        from vukery.core.errors import ConfigError
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
                base.show_slide("missing")
            with pytest.raises(ConfigError, match="on display 'apron', which isn't in displays"):
                base.show_slide("start_screen", display="apron")
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
