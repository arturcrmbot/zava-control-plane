"""In-memory ComposeSession: current stage, an event ring buffer, and an
asyncio pub/sub hub. New subscribers replay the buffered events so a browser
that connects mid-run still sees the whole story so far.
"""
from __future__ import annotations

import asyncio

_MAX_BUFFER = 2000


class ComposeSession:
    def __init__(self, compose_id: str) -> None:
        self.id = compose_id
        self.stage = "intake"
        self.done = False
        self.events: list[dict] = []
        self._subscribers: set[asyncio.Queue] = set()

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
        for q in list(self._subscribers):
            q.put_nowait(event)
