"""In-memory ComposeSession: current stage, an event ring buffer, and an
asyncio pub/sub hub. New subscribers replay the buffered events so a browser
that connects mid-run still sees the whole story so far.
"""
from __future__ import annotations

import asyncio
import time

_MAX_BUFFER = 2000


class ComposeSession:
    def __init__(self, compose_id: str) -> None:
        self.id = compose_id
        self.stage = "intake"
        self.done = False
        self.events: list[dict] = []
        self._subscribers: set[asyncio.Queue] = set()
        self.pending: dict[str, asyncio.Future] = {}
        self._t0 = time.monotonic()
        self.timeline: list[dict] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        for e in self.events:
            q.put_nowait(e)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def emit(self, event: dict) -> None:
        if event.get("type") == "stage" and event.get("stage"):
            self.stage = event["stage"]
        self.events.append(event)
        if len(self.events) > _MAX_BUFFER:
            self.events = self.events[-_MAX_BUFFER:]
        if not self.timeline:
            self._t0 = time.monotonic()
        self.timeline.append({
            "ts_offset_ms": int((time.monotonic() - self._t0) * 1000),
            "event": event,
        })
        for q in list(self._subscribers):
            q.put_nowait(event)

    def new_pending(self, request_id: str) -> asyncio.Future:
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = fut
        return fut

    def resolve(self, request_id: str, value) -> bool:
        fut = self.pending.pop(request_id, None)
        if fut and not fut.done():
            fut.set_result(value)
            return True
        return False
