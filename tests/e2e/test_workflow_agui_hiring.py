"""Emit a realistic hiring workflow event sequence on the bus and assert
the AG-UI stream produces a plausible run lifecycle.

This is not a real end-to-end hiring run — it drives the AG-UI SSE route
directly via ASGI with a synthetic FleetEvent sequence matching what a
hiring workflow actually emits, and asserts the translator produces the
full AG-UI lifecycle (RUN_STARTED → … → RUN_FINISHED).

httpx's ``ASGITransport`` buffers infinite SSE streams, so we drive the
ASGI app directly with a hand-rolled scope/receive/send, mirroring the
pattern proven in ``tests/api/routes/test_workflow_agui.py``.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from api.server.main import app
from api.server.state import app_state
from api.shared.events import FleetEvent


def _scope(run_id: str) -> dict:
    path = f"/api/workflows/{run_id}/agui"
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"test"), (b"accept", b"text/event-stream")],
        "client": ("127.0.0.1", 0),
        "server": ("test", 80),
    }


def _hiring_events(run_id: str) -> list[FleetEvent]:
    """Realistic hiring workflow event sequence."""
    return [
        FleetEvent(type="durable.workflow.started", ts=0.0,
                   workflow_id=run_id, workflow_type="hiring"),
        FleetEvent(type="durable.step.started", ts=0.1,
                   workflow_id=run_id, stage="screening"),
        FleetEvent(type="durable.executor.invoked", ts=0.2,
                   workflow_id=run_id, skill="screener"),
        FleetEvent(type="agent.completed", ts=0.3,
                   workflow_id=run_id, skill="screener",
                   output="Candidate meets minimum requirements."),
        FleetEvent(type="durable.executor.invoked", ts=0.4,
                   workflow_id=run_id, tool="policy_search",
                   args={"q": "hiring policy UK"}),
        FleetEvent(type="entity.upserted", ts=0.5,
                   workflow_id=run_id, entity_id="cand-1",
                   entity_kind="person", fields={"name": "Ada Lovelace"}),
        FleetEvent(type="durable.step.completed", ts=0.6,
                   workflow_id=run_id, stage="screening"),
        FleetEvent(type="workflow.hitl.requested", ts=0.7,
                   workflow_id=run_id, persona="hiring_manager",
                   reason="awaiting_interview_decision"),
        FleetEvent(type="durable.resumed", ts=0.8,
                   workflow_id=run_id),
        FleetEvent(type="decision.recorded", ts=0.9,
                   workflow_id=run_id, decision_id="dec-1",
                   verdict="approved", reason="strong candidate"),
        FleetEvent(type="durable.workflow.completed", ts=1.0,
                   workflow_id=run_id),
    ]


async def _drive_until_finished(run_id: str, emitter) -> list[dict]:
    seen: list[dict] = []
    finished = asyncio.Event()
    disconnect = asyncio.Event()

    async def receive():
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body":
            body = message.get("body", b"").decode()
            for line in body.splitlines():
                if not line.startswith("data:"):
                    continue
                blob = line[len("data:"):].strip()
                if not blob:
                    continue
                try:
                    payload = json.loads(blob)
                except json.JSONDecodeError:
                    continue
                seen.append(payload)
                if payload.get("type") == "RUN_FINISHED":
                    finished.set()

    app_task = asyncio.create_task(app(_scope(run_id), receive, send))
    emit_task = asyncio.create_task(emitter())
    try:
        await asyncio.wait_for(finished.wait(), timeout=10.0)
    finally:
        disconnect.set()
        emit_task.cancel()
        try:
            await emit_task
        except BaseException:
            pass
        try:
            await asyncio.wait_for(app_task, timeout=2.0)
        except BaseException:
            app_task.cancel()
            try:
                await app_task
            except BaseException:
                pass
    return seen


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_hiring_run_emits_full_agui_lifecycle():
    """Verify the AG-UI stream produces a complete lifecycle from hiring events."""
    run_id = f"hiring-{uuid.uuid4().hex[:8]}"

    async def _emit():
        # Give the route a moment to subscribe to the bus.
        await asyncio.sleep(0.1)
        for ev in _hiring_events(run_id):
            app_state.bus.emit(ev)
            await asyncio.sleep(0.01)

    seen = await _drive_until_finished(run_id, _emit)
    seen_types = [e["type"] for e in seen]

    assert "RUN_STARTED" in seen_types, f"Missing RUN_STARTED; got {seen_types}"
    assert any(t.startswith("TEXT_MESSAGE_") for t in seen_types), \
        f"No TEXT_MESSAGE events; got {seen_types}"
    assert any(t == "TOOL_CALL_START" for t in seen_types), \
        f"No TOOL_CALL_START; got {seen_types}"
    assert any(t == "STATE_DELTA" for t in seen_types), \
        f"No STATE_DELTA; got {seen_types}"
    assert "RUN_INTERRUPTED" in seen_types, \
        f"No RUN_INTERRUPTED; got {seen_types}"
    assert "RUN_FINISHED" in seen_types, f"Missing RUN_FINISHED; got {seen_types}"
    assert seen_types[-1] == "RUN_FINISHED", \
        f"Last event should be RUN_FINISHED; got {seen_types[-1]}"
