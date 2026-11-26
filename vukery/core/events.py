"""Events: the same ordering rules as MPF, so migrated games behave the same.

Written from MPF's event manager, as reference:
https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/core/events.py

The rules:

1. **Posting never runs handlers right away.** Events are queued and handled
   on the next turn of the event loop.
2. **Handlers run highest priority first.** Equal priorities run in the
   order they were added.
3. **Nested events go first.** Events posted by a handler are handled before
   the rest of the events that were already queued.
4. **Four kinds of event:**
   - normal (``post``): every handler runs;
   - boolean (``post_boolean``): a handler returning ``False`` stops the rest;
   - relay (``post_relay``): a handler returning a dict changes the
     arguments later handlers get;
   - queue (``post_queue``): handlers run one at a time, and any of them can
     ``queue.wait()`` to pause the rest until it calls ``queue.clear()``.
5. **Callbacks run after the queue empties, newest first** (MPF pops them
   off a stack).
6. **Blocking:** a handler that returns ``BLOCK`` stops lower-priority
   handlers of that event that were added with ``blockable=True``. That's
   MPF's ``|block``.
"""

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import count
from typing import Any

from vukery.core.log import get_logger

log = get_logger("events")


class Block:
    """Returned by a handler to stop lower-priority, blockable handlers of the same event."""

    def __repr__(self) -> str:
        return "BLOCK"


BLOCK = Block()


class EventHandlerError(Exception):
    """A handler raised an exception. Says which handler and event."""


@dataclass
class Handler:
    event: str
    callback: Callable[..., Any]
    priority: int
    blockable: bool
    kwargs: dict[str, Any]
    key: int

    def __repr__(self) -> str:
        name = getattr(self.callback, "__qualname__", repr(self.callback))
        return f"<{name} on {self.event!r} priority {self.priority}>"


class QueuedEvent:
    """Passed as ``queue=`` to the handlers of a queue event.

    Call ``wait()`` to hold the event until you call ``clear()``.
    """

    def __init__(self) -> None:
        self.waiting = False
        self._released: asyncio.Event | None = None

    def wait(self) -> None:
        self.waiting = True

    def clear(self) -> None:
        self.waiting = False
        if self._released:
            self._released.set()

    async def until_cleared(self) -> None:
        """Wait until ``clear()`` if ``wait()`` was called; otherwise return right away."""
        if self.waiting:
            self._released = asyncio.Event()
            await self._released.wait()


@dataclass
class _Posted:
    event: str
    kind: str  # "normal", "boolean", "relay" or "queue"
    callback: Callable[..., Any] | None
    kwargs: dict[str, Any] = field(default_factory=dict[str, Any])


class EventManager:
    """Posts events and runs their handlers."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.handlers: dict[str, list[Handler]] = {}
        self._keys = count(1)
        self._queue: deque[_Posted] = deque()
        self._callbacks: list[tuple[Callable[..., Any], dict[str, Any]]] = []
        self._queue_tasks: set[asyncio.Task[None]] = set()
        self.monitors: list[Callable[[str, dict[str, Any]], None]] = []
        self.stopped = False

    # --- handlers

    def add_handler(self, event: str, callback: Callable[..., Any], priority: int = 1,
                    blockable: bool = False, **kwargs: Any) -> Handler:
        """Run ``callback(**event_kwargs)`` when ``event`` is posted. Returns a handle for removal."""
        handler = Handler(event, callback, priority, blockable, kwargs, next(self._keys))
        handlers = self.handlers.setdefault(event, [])
        handlers.append(handler)
        handlers.sort(key=lambda h: h.priority, reverse=True)  # stable: ties keep insertion order
        return handler

    def remove_handler(self, handler: Handler) -> None:
        handlers = self.handlers.get(handler.event, [])
        if handler in handlers:
            handlers.remove(handler)
        if not handlers:
            self.handlers.pop(handler.event, None)

    def remove_handlers(self, handlers: list[Handler]) -> None:
        for handler in handlers:
            self.remove_handler(handler)

    def has_handlers(self, event: str) -> bool:
        return bool(self.handlers.get(event))

    # --- posting

    def post(self, event: str, callback: Callable[..., Any] | None = None, **kwargs: Any) -> None:
        self._post(_Posted(event, "normal", callback, kwargs))

    def post_boolean(self, event: str, callback: Callable[..., Any] | None = None, **kwargs: Any) -> None:
        self._post(_Posted(event, "boolean", callback, kwargs))

    def post_relay(self, event: str, callback: Callable[..., Any] | None = None, **kwargs: Any) -> None:
        self._post(_Posted(event, "relay", callback, kwargs))

    def post_queue(self, event: str, callback: Callable[..., Any] | None = None, **kwargs: Any) -> None:
        self._post(_Posted(event, "queue", callback, kwargs))

    async def post_async(self, event: str, **kwargs: Any) -> dict[str, Any]:
        """Post and wait until it's been handled."""
        return await self._post_and_wait(event, "normal", kwargs)

    async def post_queue_async(self, event: str, **kwargs: Any) -> dict[str, Any]:
        """Post a queue event and wait until every handler has released it."""
        return await self._post_and_wait(event, "queue", kwargs)

    async def post_relay_async(self, event: str, **kwargs: Any) -> dict[str, Any]:
        """Post a relay event and wait. Returns the arguments as the handlers left them."""
        return await self._post_and_wait(event, "relay", kwargs)

    async def _post_and_wait(self, event: str, kind: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        future: asyncio.Future[dict[str, Any]] = self.loop.create_future()

        def done(**result: Any) -> None:
            if not future.done():
                future.set_result(result)

        self._post(_Posted(event, kind, done, kwargs))
        return await future

    def _post(self, posted: _Posted) -> None:
        if self.stopped:
            log.warning("Event posted after stop: %s", posted.event)
            return
        log.debug("Event: %s %s", posted.event, posted.kwargs or "")
        for monitor in self.monitors:
            monitor(posted.event, dict(posted.kwargs))
        if not posted.callback and posted.event not in self.handlers:
            return
        if not self._queue:
            self.loop.call_soon(self._process)
        self._queue.append(posted)

    def stop(self) -> None:
        self.stopped = True
        for task in self._queue_tasks:
            task.cancel()

    # --- processing (MPF's process_event_queue, rule 3 and 5)

    def _process(self) -> None:
        inner: deque[deque[_Posted]] = deque()
        while self._queue or self._callbacks:
            if self._queue:
                current, self._queue = self._queue, deque()
                while current:
                    posted = current.popleft()
                    if not current and inner:
                        current = inner.popleft()
                    self._handle(posted)
                    if self._queue:  # handlers posted more: those go first
                        inner.appendleft(current)
                        current, self._queue = self._queue, deque()
            if self._callbacks:
                callback, kwargs = self._callbacks.pop()  # newest first
                callback(**kwargs)

    def _handle(self, posted: _Posted) -> None:
        match posted.kind:
            case "queue":
                if posted.event in self.handlers:
                    task = self.loop.create_task(self._run_queue(posted))
                    self._queue_tasks.add(task)
                    task.add_done_callback(self._queue_task_done)
                elif posted.callback:
                    self._callbacks.append((posted.callback, posted.kwargs))
            case _:
                result = self._run_handlers(posted)
                if posted.callback:
                    if result is not None and posted.kind != "normal":
                        posted.kwargs["ev_result"] = result
                    self._callbacks.append((posted.callback, posted.kwargs))

    def _queue_task_done(self, task: asyncio.Task[None]) -> None:
        self._queue_tasks.discard(task)
        if not task.cancelled() and task.exception():
            raise task.exception()  # type: ignore[misc]

    def _run_handlers(self, posted: _Posted) -> Any:
        kwargs = posted.kwargs
        blocked_below: int | None = None
        result: Any = None
        for handler in list(self.handlers.get(posted.event, [])):
            if handler.blockable and blocked_below is not None and handler.priority < blocked_below:
                continue
            merged = {**kwargs, **handler.kwargs}
            try:
                outcome = handler.callback(**merged)
            except Exception as e:
                raise EventHandlerError(f"{handler} failed on event {posted.event!r}: {e}") from e
            match posted.kind, outcome:
                case "boolean", False:
                    return False
                case "relay", dict():
                    changes: dict[str, Any] = outcome  # type: ignore[assignment]
                    kwargs.update(changes)
                    result = kwargs
                case _, Block():
                    blocked_below = handler.priority if blocked_below is None else max(blocked_below,
                                                                                         handler.priority)
                case _:
                    pass
        return True if posted.kind == "boolean" else result

    async def _run_queue(self, posted: _Posted) -> None:
        for handler in list(self.handlers.get(posted.event, [])):
            queue = QueuedEvent()
            try:
                handler.callback(queue=queue, **{**posted.kwargs, **handler.kwargs})
            except Exception as e:
                raise EventHandlerError(f"{handler} failed on event {posted.event!r}: {e}") from e
            await queue.until_cleared()
        if posted.callback:
            posted.callback(**posted.kwargs)
