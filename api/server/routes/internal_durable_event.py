from __future__ import annotations
import time
import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from api.server.state import app_state
from api.server.services.exception_factory import (
    compose_hitl_exception, compose_validator_exception
)
from api.shared.events import FleetEvent
from api.shared.types import Phase, OtelSpan, ActionLedgerEntry, McpCall

router = APIRouter(prefix="/internal")

# Executor span start times, keyed by (workflow_id, executor_name) so we can
# compute end_ms when stage=complete/error arrives.
_span_starts: dict[tuple[str, str], float] = {}


class DurableEventBody(BaseModel):
    workflow_id: str
    instance_id: str | None = None
    kind: str
    payload: dict


def _ledger(wid: str, *, kind: str, actor_id: str, action: str, details: dict, revocable: bool = False) -> None:
    app_state.store.append_ledger(wid, ActionLedgerEntry(
        workflow_id=wid,
        timestamp=time.time(),
        actor_kind=kind,  # type: ignore[arg-type]
        actor_id=actor_id,
        action=action,
        revocable=revocable,
        details=details,
    ))


@router.post("/durable-event")
async def receive_durable_event(body: DurableEventBody):
    wid = body.workflow_id
    now = time.time()

    app_state.orchestration_history.setdefault(wid, []).append({
        "kind": body.kind, "payload": body.payload, "at": now
    })
    app_state.hub.broadcast("orchestration", {
        "kind": body.kind, "workflow_id": wid, "payload": body.payload
    })

    if body.kind == "workflow.started":
        app_state.bus.emit(FleetEvent(type="workflow.started", workflow_id=wid))
        _ledger(wid, kind="agent", actor_id="orchestrator",
                action="workflow.started", details={})

    elif body.kind == "step.started":
        step = body.payload.get("step")
        if step:
            # Idempotent: Durable Functions may replay; skip if phase exists.
            if not any(p.name == step for p in app_state.store.get_phases(wid)):
                app_state.store.append_phase(wid, Phase(
                    workflow_id=wid, name=step,  # type: ignore[arg-type]
                    status="in_progress", started_at=now,
                ))
            # Sync the workflow's current_phase so the UI reflects progression
            # past Intake. The orchestrator advances through phases internally,
            # but nothing was lifting that state up to the workflow record.
            w = app_state.store.get_workflow(wid)
            if w:
                w.current_phase = step  # type: ignore[assignment]
            app_state.bus.emit(FleetEvent(
                type="workflow.phase.started", workflow_id=wid, phase=step
            ))

    elif body.kind == "step.completed":
        step = body.payload.get("step")
        dur = body.payload.get("duration_ms", 0)
        if step:
            app_state.store.update_phase(wid, step, status="completed", completed_at=now)
            _ledger(wid, kind="agent", actor_id=f"phase:{step}",
                    action=f"phase.completed:{step}", details={"duration_ms": dur})
            app_state.bus.emit(FleetEvent(
                type="workflow.phase.completed", workflow_id=wid,
                phase=step, durationMs=dur,
            ))

    elif body.kind == "executor.invoked":
        name = str(body.payload.get("name", "?"))
        stage = body.payload.get("stage")
        etype = str(body.payload.get("type", "?"))
        if stage == "start":
            _span_starts[(wid, name)] = now
        elif stage in ("complete", "error"):
            dur_s = body.payload.get("duration_ms", 0) / 1000.0
            start = _span_starts.pop((wid, name), now - dur_s)
            app_state.store.append_span(OtelSpan(
                trace_id=wid,  # group all spans under the workflow id as trace
                span_id=uuid.uuid4().hex[:16],
                name=f"executor.{name}",
                start_ms=start * 1000,
                end_ms=(start + dur_s) * 1000,
                attributes={
                    "workflow.id": wid,
                    "executor.name": name,
                    "executor.type": etype,
                },
                status="error" if stage == "error" else "ok",
            ))

    elif body.kind == "mcp.call":
        p = body.payload
        app_state.store.append_mcp_call(McpCall(
            workflow_id=wid,
            timestamp=now,
            tool=p.get("tool", "?"),
            url=p.get("url", ""),
            method=p.get("method", "POST"),
            request=p.get("request", {}),
            response=p.get("response", {}),
            status_code=int(p.get("status_code", 0)),
            duration_ms=int(p.get("duration_ms", 0)),
        ))

    elif body.kind == "validator.blocked":
        compose_validator_exception(
            app_state.store, wid,
            body.payload.get("validator") or body.payload.get("name", "unknown"),
            body.payload.get("reason", "validation failed"),
        )
        _ledger(wid, kind="agent",
                actor_id=f"validator:{body.payload.get('name', 'unknown')}",
                action="validator.blocked",
                details={"reason": body.payload.get("reason", "validation failed")})
        app_state.bus.emit(FleetEvent(
            type="workflow.exception.detected", workflow_id=wid,
            category="validator-blocked", severity="high",
        ))

    elif body.kind == "suspended":
        compose_hitl_exception(
            app_state.store, wid,
            body.payload.get("reason", "approval"),
        )
        _ledger(wid, kind="agent", actor_id="orchestrator",
                action="suspended",
                details={"reason": body.payload.get("reason", "approval")})
        w = app_state.store.get_workflow(wid)
        if w:
            w.status = "awaiting_hitl"
        app_state.bus.emit(FleetEvent(
            type="workflow.hitl.requested", workflow_id=wid,
            reason=body.payload.get("reason", "approval"),
        ))

    elif body.kind == "resumed":
        _ledger(wid, kind="agent", actor_id="orchestrator",
                action="resumed", details={})
        w = app_state.store.get_workflow(wid)
        if w:
            w.status = "in_progress"

    elif body.kind == "workflow.completed":
        _ledger(wid, kind="agent", actor_id="orchestrator",
                action="workflow.completed", details={})
        w = app_state.store.get_workflow(wid)
        if w:
            w.status = "completed"
        app_state.bus.emit(FleetEvent(
            type="workflow.resolved", workflow_id=wid, resolution="completed"
        ))

    elif body.kind == "workflow.rejected":
        _ledger(wid, kind="human",
                actor_id=body.payload.get("by") or "operator",
                action="workflow.rejected",
                details={"reason": body.payload.get("reason", "operator rejected")})
        app_state.bus.emit(FleetEvent(
            type="workflow.resolved", workflow_id=wid, resolution="rejected"
        ))
        w = app_state.store.get_workflow(wid)
        if w:
            w.status = "failed"
            w.current_phase = "Approval"

    return {"received": True}
