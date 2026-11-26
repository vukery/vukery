"""The media protocol: what a media controller knows, and the engine's socket server."""

import asyncio
from pathlib import Path

import pytest

from vukery.core.clock import RealClock
from vukery.core.machine import Machine
from vukery.mc.state import MediaState
from vukery.media import protocol
from vukery.media.slides import Slide, Text

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
        assert [t.text for t in state.texts("main")] == ["12,340", "BALL 2", ""]

    def it_follows_player_changes_and_turns():
        state = MediaState()
        state.apply(welcome())
        state.apply({"type": "player", "number": 2, "vars": {"score": 50, "ball": 1}})
        state.apply({"type": "turn", "number": 2})
        assert [t.text for t in state.texts("main")][:2] == ["50", "BALL 1"]

    def it_shows_nothing_for_an_unknown_or_empty_slide():
        state = MediaState()
        state.apply(welcome())
        state.apply({"type": "show", "display": "main", "slide": None})
        assert state.texts("main") == []

    def it_ignores_messages_it_doesnt_know():  # so the protocol can grow
        state = MediaState()
        state.apply(welcome())
        state.apply({"type": "something_new", "x": 1})
        assert state.connected

    def it_notices_the_engine_stopping():
        state = MediaState()
        state.apply({"type": "bye"})
        assert state.engine_stopped


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
            assert message["type"] == "welcome"
            assert message["showing"] == {"main": "start_screen"}
            assert set(message["slides"]) == {"start_screen", "score"}
            assert message["displays"] == {"main": {"width": 800, "height": 480}}
        finally:
            machine.stop("test")
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(asyncio.sleep(0))
            loop.close()
