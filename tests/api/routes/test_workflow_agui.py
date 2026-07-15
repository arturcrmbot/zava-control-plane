"""Tests for the per-workflow AG-UI SSE drill-in route.

The endpoint is an infinite SSE stream — httpx's ``ASGITransport`` buffers
the entire response before returning, so we drive the ASGI app directly
with a hand-rolled scope/receive/send. Disconnect is signalled to the
generator via ``http.disconnect`` once the expected event has been seen.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from api.server.main import app
from api.server.routes.workflow_agui import _history_to_fleet_events
from api.server.services.substrate_to_agui import SubstrateToAGUI
from api.server.state import app_state
from api.shared.agui_events import to_sse_dict
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
        "headers": [(b"host", b"test")],
        "client": ("127.0.0.1", 0),
        "server": ("test", 80),
    }


async def _drive_until_finished(run_id: str, emitter) -> list[dict]:
    """Run the ASGI app against a synthetic scope, collect SSE payloads.

    Returns the list of JSON-decoded ``data:`` payloads up to and
    including ``RUN_FINISHED``. ``emitter`` is an awaitable that pushes
    bus events into ``app_state.bus`` once the route is subscribed.
    """
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
        await asyncio.wait_for(finished.wait(), timeout=5.0)
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
async def test_run_started_and_finished_round_trip():
    async def _emit():
        await asyncio.sleep(0.1)
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.started",
            ts=0.0, workflow_id="hiring-42",
            workflow_type="hiring"))
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.completed",
            ts=0.0, workflow_id="hiring-42"))

    seen = await _drive_until_finished("hiring-42", _emit)
    types = [e["type"] for e in seen]
    assert types == ["RUN_STARTED", "RUN_FINISHED"]


@pytest.mark.asyncio
async def test_other_run_events_are_filtered_out():
    async def _emit():
        await asyncio.sleep(0.1)
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.started",
            ts=0.0, workflow_id="other-run",
            workflow_type="hiring"))
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.completed",
            ts=0.0, workflow_id="hiring-42"))

    seen = await _drive_until_finished("hiring-42", _emit)
    types = [e["type"] for e in seen]
    assert "RUN_STARTED" not in types
    assert types == ["RUN_FINISHED"]


def test_failed_history_replays_run_error_without_run_finished():
    events = _history_to_fleet_events(
        "care-failed",
        {
            "kind": "workflow.failed",
            "at": 1.0,
            "payload": {"reason": "approval denied"},
        },
    )
    translator = SubstrateToAGUI("care-failed")

    payloads = [
        to_sse_dict(event)
        for fleet_event in events
        for event in translator.translate(fleet_event)
    ]

    assert [payload["type"] for payload in payloads] == ["RUN_ERROR"]
    assert payloads[0]["message"] == "approval denied"
