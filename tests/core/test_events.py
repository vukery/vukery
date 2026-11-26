"""The event manager follows MPF's ordering rules (see vukery/core/events.py)."""

import asyncio

import pytest

from vukery.core.clock import settle
from vukery.core.events import BLOCK, Block, EventHandlerError, EventManager


@pytest.fixture
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def events(loop):
    return EventManager(loop)


def describe_events():
    def it_never_runs_handlers_while_posting(events, loop):
        seen = []
        events.add_handler("ping", lambda: seen.append("handled"))
        events.post("ping")
        assert seen == []
        settle(loop)
        assert seen == ["handled"]

    def it_passes_event_arguments_and_handler_arguments(events, loop):
        seen = []
        events.add_handler("score", lambda points, who: seen.append((points, who)), who="base")
        events.post("score", points=500)
        settle(loop)
        assert seen == [(500, "base")]

    def describe_handler_order():
        def it_runs_higher_priority_first(events, loop):
            seen = []
            events.add_handler("e", lambda: seen.append("low"), priority=1)
            events.add_handler("e", lambda: seen.append("high"), priority=100)
            events.post("e")
            settle(loop)
            assert seen == ["high", "low"]

        def it_runs_equal_priorities_in_the_order_added(events, loop):
            seen = []
            for name in ("first", "second", "third"):
                events.add_handler("e", lambda n=name: seen.append(n), priority=5)
            events.post("e")
            settle(loop)
            assert seen == ["first", "second", "third"]

        def it_stops_calling_removed_handlers(events, loop):
            seen = []
            handler = events.add_handler("e", lambda: seen.append("x"))
            events.remove_handler(handler)
            events.post("e")
            settle(loop)
            assert seen == []

    def describe_nested_events():
        def it_handles_events_posted_by_a_handler_before_the_rest_of_the_queue(events, loop):
            seen = []
            events.add_handler("a", lambda: (seen.append("a"), events.post("a_child")))
            events.add_handler("a_child", lambda: seen.append("a_child"))
            events.add_handler("b", lambda: seen.append("b"))
            events.post("a")
            events.post("b")
            settle(loop)
            assert seen == ["a", "a_child", "b"]

    def describe_callbacks():
        def it_runs_callbacks_after_the_queue_is_empty_newest_first(events, loop):
            seen = []
            events.add_handler("a", lambda: seen.append("handler a"))
            events.add_handler("b", lambda: seen.append("handler b"))
            events.post("a", callback=lambda: seen.append("callback a"))
            events.post("b", callback=lambda: seen.append("callback b"))
            settle(loop)
            assert seen == ["handler a", "handler b", "callback b", "callback a"]

        def it_runs_a_callback_even_without_handlers(events, loop):
            seen = []
            events.post("nobody_listens", callback=lambda: seen.append("done"))
            settle(loop)
            assert seen == ["done"]

    def describe_boolean_events():
        def it_stops_at_the_first_false(events, loop):
            seen = []
            events.add_handler("may_start", lambda: (seen.append("veto"), False)[1], priority=10)
            events.add_handler("may_start", lambda: seen.append("never"), priority=1)
            results = []
            events.post_boolean("may_start", callback=lambda ev_result: results.append(ev_result))
            settle(loop)
            assert seen == ["veto"]
            assert results == [False]

        def it_reports_true_when_nobody_objects(events, loop):
            events.add_handler("may_start", lambda: None)
            results = []
            events.post_boolean("may_start", callback=lambda ev_result: results.append(ev_result))
            settle(loop)
            assert results == [True]

    def describe_relay_events():
        def it_lets_handlers_change_the_arguments(events, loop):
            seen = []
            events.add_handler("target", lambda target: {"target": "upper"}, priority=10)
            events.add_handler("target", lambda target: seen.append(target), priority=1)
            events.post_relay("target", target="playfield")
            settle(loop)
            assert seen == ["upper"]

    def describe_queue_events():
        def it_pauses_until_the_waiting_handler_clears(events, loop):
            seen = []
            held = []

            def hold(queue):
                seen.append("first")
                queue.wait()
                held.append(queue)

            events.add_handler("ball_ending", hold, priority=10)
            events.add_handler("ball_ending", lambda queue: seen.append("second"), priority=1)
            events.post_queue("ball_ending", callback=lambda: seen.append("done"))
            settle(loop)
            assert seen == ["first"]
            held[0].clear()
            settle(loop)
            assert seen == ["first", "second", "done"]

        def it_can_be_awaited(events, loop):
            seen = []
            events.add_handler("game_starting", lambda queue: seen.append("handled"))

            async def start():
                await events.post_queue_async("game_starting")
                seen.append("after")

            loop.run_until_complete(start())
            assert seen == ["handled", "after"]

    def describe_blocking():
        def it_stops_lower_priority_blockable_handlers(events, loop):
            seen = []
            events.add_handler("s_pop_active", lambda: (seen.append("mode"), BLOCK)[1], priority=200,
                               facility="score")
            events.add_handler("s_pop_active", lambda: seen.append("base"), priority=100, facility="score")
            events.post("s_pop_active")
            settle(loop)
            assert seen == ["mode"]

        def it_doesnt_stop_handlers_that_arent_blockable(events, loop):
            seen = []
            events.add_handler("s_pop_active", lambda: BLOCK, priority=200, facility="score")
            events.add_handler("s_pop_active", lambda: seen.append("audit"), priority=100)
            events.post("s_pop_active")
            settle(loop)
            assert seen == ["audit"]

        def it_stops_only_the_named_facility(events, loop):
            seen = []
            events.add_handler("s_pop_active", lambda: Block("score"), priority=200, facility="score")
            events.add_handler("s_pop_active", lambda: seen.append("base score"), priority=100, facility="score")
            events.add_handler("s_pop_active", lambda: seen.append("base sound"), priority=100,
                               facility="handlers")
            events.post("s_pop_active")
            settle(loop)
            assert seen == ["base sound"]

        def it_doesnt_stop_handlers_at_the_same_priority(events, loop):
            seen = []
            events.add_handler("e", lambda: BLOCK, priority=100, facility="score")
            events.add_handler("e", lambda: seen.append("same priority"), priority=100, facility="score")
            events.post("e")
            settle(loop)
            assert seen == ["same priority"]

    def describe_errors():
        def it_says_which_handler_failed_on_which_event(events, loop):
            def broken():
                raise ValueError("oops")

            events.add_handler("e", broken)
            events.post("e")
            with pytest.raises(EventHandlerError, match="broken.*'e'.*oops"):
                settle(loop)
