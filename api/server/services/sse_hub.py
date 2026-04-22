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

    async def stream(self, topic: Topic) -> AsyncIterator[str]:
        q = self.subscribe(topic)
        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            self.unsubscribe(topic, q)
