# src/server/services/fleet_manager_queue.py
from __future__ import annotations
import asyncio
from typing import Awaitable, Callable
from pydantic import BaseModel


class QueueEntry(BaseModel):
    workflow_id: str | None = None
    reason: str


class FleetManagerQueue:
    def __init__(self, processor: Callable[[list[QueueEntry]], Awaitable[None]], debounce_ms: int = 2000):
        self._processor = processor
        self._debounce = debounce_ms / 1000.0
        self._pending: dict[str, QueueEntry] = {}
        self._task: asyncio.Task | None = None
        self._flushing = False

    def enqueue(self, entry: QueueEntry) -> None:
        # Workflow-bound events de-dupe by workflow_id so the same workflow's
        # rapid-fire events collapse into one wake. Workflow-less events
        # (fleet.tick, fleet.anomaly.detected) get a per-reason sentinel key so
        # tick + anomaly arriving in the same debounce window don't clobber
        # each other.
        key = entry.workflow_id or f"__fleet__:{entry.reason}"
        self._pending[key] = entry
        if not self._task or self._task.done():
            self._task = asyncio.get_event_loop().create_task(self._wait_and_flush())

    def depth(self) -> int:
        return len(self._pending)

    async def _wait_and_flush(self) -> None:
        await asyncio.sleep(self._debounce)
        if self._flushing:
            return
        self._flushing = True
        try:
            batch = list(self._pending.values())
            self._pending.clear()
            if batch:
                await self._processor(batch)
        finally:
            self._flushing = False
