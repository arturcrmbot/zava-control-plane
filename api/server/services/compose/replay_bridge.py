"""ReplayBridge: drive a ComposeSession from a recorded tape.

Fills the same role as ComposeBridge (it makes a session emit events) but from
a tape instead of a live agent — no subprocess, no tree mutation. HITL events
optionally pause using the session's existing pending-future mechanism, so the
Phase-3 /answer + /brief endpoints resume replay exactly as in a live run.
"""
from __future__ import annotations

import asyncio
import uuid

_MAX_GAP_S = 2.5  # compress long "thinking" pauses so a 10-min run replays fast
_HITL_TIMEOUT_S = 300


class ReplayBridge:
    def __init__(self, session, tape: list[dict], speed: float = 8.0,
                 pause_on_hitl: bool = False) -> None:
        self.session = session
        self.tape = tape
        self.speed = max(speed, 0.1)
        self.pause_on_hitl = pause_on_hitl
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        # Retain the handle so the task can't be garbage-collected mid-run.
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        prev = 0
        try:
            for entry in self.tape:
                gap = (entry.get("ts_offset_ms", prev) - prev) / 1000.0 / self.speed
                if gap > 0:
                    await asyncio.sleep(min(gap, _MAX_GAP_S))
                prev = entry.get("ts_offset_ms", prev)

                event = dict(entry.get("event") or {})
                if self.pause_on_hitl and event.get("type") in ("question", "brief"):
                    rid = uuid.uuid4().hex
                    event["request_id"] = rid
                    fut = self.session.new_pending(rid)
                    self.session.emit(event)
                    try:
                        await asyncio.wait_for(fut, timeout=_HITL_TIMEOUT_S)
                    except asyncio.TimeoutError:
                        pass
                else:
                    self.session.emit(event)
        finally:
            self.session.finish("Replay complete")
