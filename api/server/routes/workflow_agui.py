"""AG-UI compatible per-workflow SSE drill-in.

Replays historical events from orchestration_history on connect, then
streams live events from the EventBus.
"""
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

# Maps orchestration_history `kind` to the FleetEvent type(s) to emit.
# Each entry is (fleet_event_type, payload_extractor).
_KIND_FLEET_MAP: dict[str, list[tuple[str, Any]]] = {}


def _history_to_fleet_events(
    run_id: str, entry: dict[str, Any]
) -> list[FleetEvent]:
    """Convert one orchestration_history entry to FleetEvent(s)."""
    kind = entry.get("kind", "")
    payload = entry.get("payload") or {}
    ts = entry.get("at", 0.0)
    events: list[FleetEvent] = []

    if kind == "workflow.started":
        events.append(FleetEvent(
            type="durable.workflow.started", ts=ts, workflow_id=run_id,
            workflow_type=payload.get("workflow_type")))

    elif kind == "step.started":
        step = payload.get("step")
        if step:
            events.append(FleetEvent(
                type="durable.step.started", ts=ts, workflow_id=run_id,
                phase=step, step=step))

    elif kind == "step.completed":
        step = payload.get("step")
        if step:
            events.append(FleetEvent(
                type="durable.step.completed", ts=ts, workflow_id=run_id,
                phase=step, step=step))

    elif kind == "executor.invoked":
        name = str(payload.get("name", "?"))
        etype = str(payload.get("type", "?"))
        attrs = payload.get("attributes") or {}
        skill_label = None
        if etype == "agent":
            skill_label = name[len("agent_"):] if name.startswith("agent_") else name
        elif etype == "validator":
            skill_label = name
        events.append(FleetEvent(
            type="durable.executor.invoked", ts=ts, workflow_id=run_id,
            name=name, executor_type=etype,
            stage=payload.get("stage"),
            skill=attrs.get("skill") or attrs.get("skill_label") or skill_label,
            tool=attrs.get("tool")))

    elif kind == "tool.invoked":
        p = payload
        events.append(FleetEvent(
            type="durable.executor.invoked", ts=ts, workflow_id=run_id,
            name=f"tool:{p.get('tool', '?')}",
            executor_type="tool",
            skill=p.get("skill"), tool=p.get("tool")))

    elif kind == "agent_output":
        agent = str(payload.get("agent") or "")
        output = payload.get("output")
        if agent:
            emit_payload: dict[str, Any] = {"skill": agent}
            if output is not None:
                out_str = (json.dumps(output) if isinstance(output, dict)
                           else str(output))
                emit_payload["output"] = out_str
            events.append(FleetEvent(
                type="agent.completed", ts=ts, workflow_id=run_id,
                **emit_payload))

    elif kind == "validator.blocked":
        events.append(FleetEvent(
            type="durable.validator.blocked", ts=ts, workflow_id=run_id,
            name=payload.get("name", "unknown"),
            reason=payload.get("reason", "validation failed")))

    elif kind == "suspended":
        reason = payload.get("reason", "approval")
        events.append(FleetEvent(
            type="workflow.hitl.requested", ts=ts, workflow_id=run_id,
            reason=reason, persona=payload.get("persona")))

    elif kind == "resumed":
        events.append(FleetEvent(
            type="durable.resumed", ts=ts, workflow_id=run_id,
            phase=payload.get("phase")))

    elif kind == "workflow.completed":
        events.append(FleetEvent(
            type="durable.workflow.completed", ts=ts, workflow_id=run_id,
            status="completed"))

    elif kind == "workflow.failed":
        events.append(FleetEvent(
            type="workflow.failed", ts=ts, workflow_id=run_id,
            reason=payload.get("reason", "workflow failed")))

    return events


@router.get("/api/workflows/{run_id}/agui")
async def workflow_agui_stream(run_id: str,
                               request: Request) -> EventSourceResponse:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=400)
    loop = asyncio.get_running_loop()
    translator = SubstrateToAGUI(run_id=run_id)

    # ── Replay historical events ────────────────────────────────────
    history = app_state.orchestration_history.get(run_id, [])
    for entry in history:
        for fe in _history_to_fleet_events(run_id, entry):
            for agui_ev in translator.translate(fe):
                try:
                    queue.put_nowait(to_sse_dict(agui_ev))
                except asyncio.QueueFull:
                    break

    # ── Subscribe to live events ────────────────────────────────────
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
