"""The virtual clock that tests run on."""

import asyncio

import pytest

from vukery.core.clock import VirtualClock
from vukery.testing import expect


@pytest.fixture
def clock():
    loop = asyncio.new_event_loop()
    yield VirtualClock(loop)
    loop.close()


def describe_virtual_clock():
    def it_only_moves_when_advanced(clock):
        expect(clock.now()).to_equal(0)
        clock.advance(2.5)
        expect(clock.now()).to_equal(2.5)

    def it_runs_due_timers_in_order(clock):
        fired = []
        clock.call_later(2, fired.append, "two")
        clock.call_later(1, fired.append, "one")
        clock.advance(1.5)
        expect(fired).to_equal(["one"])
        clock.advance(1)
        expect(fired).to_equal(["one", "two"])

    def it_runs_timers_at_their_own_time(clock):
        seen = []
        clock.call_later(1, lambda: seen.append(clock.now()))
        clock.advance(10)
        expect(seen).to_equal([1])

    def it_skips_cancelled_timers(clock):
        fired = []
        timer = clock.call_later(1, fired.append, "x")
        timer.cancel()
        clock.advance(2)
        expect(fired).to_equal([])

    def it_wakes_sleeping_coroutines(clock):
        log = []

        async def ball():
            log.append(("start", clock.now()))
            await clock.sleep(3)
            log.append(("end", clock.now()))

        clock.loop.create_task(ball())
        clock.advance(0)
        expect(log).to_equal([("start", 0)])
        clock.advance(3)
        expect(log).to_equal([("start", 0), ("end", 3)])

    def it_runs_timers_that_timers_add_within_the_same_advance(clock):
        fired = []
        clock.call_later(1, lambda: clock.call_later(1, fired.append, "second"))
        clock.advance(2)
        expect(fired).to_equal(["second"])
