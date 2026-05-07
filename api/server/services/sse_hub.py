from __future__ import annotations
import asyncio
import json
from typing import Any, AsyncIterator, Literal

Topic = Literal["fleet", "fleet-manager", "orchestration"]


class SSEHub:
    def __init__(self) -> None:
        self._queues: dict[Topic, set[asyncio.Queue]] = {
            "fleet": set(), "fleet-manager": set(), "orchestration": set()
        }

    def subscribe(self, topic: Topic) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._queues[topic].add(q)
        return q

    def unsubscribe(self, topic: Topic, q: asyncio.Queue) -> None:
        self._queues[topic].discard(q)

    def broadcast(self, topic: Topic, data: Any) -> None:
        payload = json.dumps(data, default=str)
        for q in list(self._queues[topic]):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def stream(self, topic: Topic, request: Any | None = None) -> AsyncIterator[str]:
        """Yield queued messages for `topic` until the client disconnects.

        When `request` is supplied (a Starlette/FastAPI Request), the loop
        wakes every 15s to check `request.is_disconnected()` and yields a
        heartbeat ":\\n\\n" comment so intermediaries (proxies, load
        balancers) don't reap the idle connection. Without this poll, a
        suspended `await q.get()` keeps the subscriber alive across client
        teardowns, which over an open/close cycle leaks queues + listeners.
        """
        q = self.subscribe(topic)
        try:
            while True:
                if request is None:
                    msg = await q.get()
                    yield msg
                    continue
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    # SSE comment line keeps the connection alive without
                    # triggering an event handler client-side.
                    yield ":\n\n"
        finally:
            self.unsubscribe(topic, q)
