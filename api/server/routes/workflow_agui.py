"""AG-UI compatible per-workflow SSE drill-in."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from api.server.services.substrate_to_agui import SubstrateToAGUI
from api.server.state import app_state
from api.shared.agui_events import to_sse_dict
from api.shared.events import FleetEvent

router = APIRouter()


@router.get("/api/workflows/{run_id}/agui")
async def workflow_agui_stream(run_id: str,
                               request: Request) -> EventSourceResponse:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=400)
    loop = asyncio.get_running_loop()
    translator = SubstrateToAGUI(run_id=run_id)

    def _push(event: FleetEvent) -> None:
        for agui_ev in translator.translate(event):
            try:
                loop.call_soon_threadsafe(
                    queue.put_nowait, to_sse_dict(agui_ev))
            except (RuntimeError, asyncio.QueueFull):
                pass

    unsubscribe = app_state.bus.on_any(_push)

    async def _gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
                    continue
                yield {"data": json.dumps(payload)}
        finally:
            unsubscribe()

    return EventSourceResponse(_gen())
