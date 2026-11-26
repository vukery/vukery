"""The machine clock: real time on a machine, virtual time in tests.

All engine timing (delays, timers, ``await clock.sleep()``) goes through a
``Clock``, never ``asyncio.sleep`` directly, so tests can jump time forward
and get exactly the same behavior as on a machine, only instantly.

- ``RealClock`` wraps the asyncio event loop's own clock.
- ``VirtualClock`` keeps its own time. Nothing happens until ``advance()``,
  which runs every timer that comes due, in order, and lets the event loop
  finish all the work each one triggers before moving on.
"""

import asyncio
import heapq
import itertools
from collections.abc import Callable
from typing import Any, Protocol


class Timer(Protocol):
    def cancel(self) -> None: ...


class Clock(Protocol):
    loop: asyncio.AbstractEventLoop

    def now(self) -> float:
        """Seconds since the clock started."""
        ...

    def call_later(self, seconds: float, callback: Callable[..., Any], *args: Any) -> Timer: ...

    async def sleep(self, seconds: float) -> None: ...


class RealClock:
    """Real time, from the asyncio event loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self._start = loop.time()

    def now(self) -> float:
        return self.loop.time() - self._start

    def call_later(self, seconds: float, callback: Callable[..., Any], *args: Any) -> Timer:
        return self.loop.call_later(max(seconds, 0.0), callback, *args)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class _VirtualTimer:
    def __init__(self, when: float, callback: Callable[..., Any], args: tuple[Any, ...]):
        self.when = when
        self.callback = callback
        self.args = args
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


def settle(loop: asyncio.AbstractEventLoop, max_rounds: int = 10_000) -> None:
    """Run the event loop until nothing is left to do right now (no ready callbacks).

    An exception raised in any callback or task during that time is re-raised
    here, so tests fail on it instead of it only being logged.
    """
    errors: list[BaseException] = []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda _, context: errors.append(
        context.get("exception") or RuntimeError(context.get("message", "event loop error"))))

    async def until_idle() -> None:
        idle_rounds = 0
        for _ in range(max_rounds):
            await asyncio.sleep(0)
            ready = len(getattr(loop, "_ready", ()))
            idle_rounds = idle_rounds + 1 if ready == 0 else 0
            if idle_rounds >= 2:
                return
        raise RuntimeError("The event loop never went idle (something keeps scheduling work)")

    try:
        loop.run_until_complete(until_idle())
    finally:
        loop.set_exception_handler(previous)
    if errors:
        raise errors[0]


class VirtualClock:
    """Time that only moves when ``advance()`` is called. For tests."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self._now = 0.0
        self._timers: list[tuple[float, int, _VirtualTimer]] = []
        self._order = itertools.count()

    def now(self) -> float:
        return self._now

    def call_later(self, seconds: float, callback: Callable[..., Any], *args: Any) -> Timer:
        timer = _VirtualTimer(self._now + max(seconds, 0.0), callback, args)
        heapq.heappush(self._timers, (timer.when, next(self._order), timer))
        return timer

    async def sleep(self, seconds: float) -> None:
        future = self.loop.create_future()
        self.call_later(seconds, lambda: future.done() or future.set_result(None))
        await future

    def advance(self, seconds: float = 0.0) -> None:
        """Move time forward, running every timer that comes due (and everything it triggers)."""
        target = self._now + max(seconds, 0.0)
        settle(self.loop)
        while self._timers and self._timers[0][0] <= target:
            when, _, timer = heapq.heappop(self._timers)
            if timer.cancelled:
                continue
            self._now = max(self._now, when)
            timer.callback(*timer.args)
            settle(self.loop)
        self._now = target
        settle(self.loop)
