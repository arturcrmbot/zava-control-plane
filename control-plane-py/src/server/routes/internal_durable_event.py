from __future__ import annotations
import time
from fastapi import APIRouter
from pydantic import BaseModel
from src.server.state import app_state
from src.server.services.exception_factory import (
    compose_hitl_exception, compose_validator_exception
)
from src.shared.events import FleetEvent

router = APIRouter(prefix="/internal")


class DurableEventBody(BaseModel):
    workflow_id: str
    instance_id: str | None = None
    kind: str
    payload: dict


@router.post("/durable-event")
async def receive_durable_event(body: DurableEventBody):
    app_state.orchestration_history.setdefault(body.workflow_id, []).append({
        "kind": body.kind, "payload": body.payload, "at": time.time()
    })
    app_state.hub.broadcast("orchestration", {
        "kind": body.kind, "workflow_id": body.workflow_id, "payload": body.payload
    })
    if body.kind == "workflow.started":
        app_state.bus.emit(FleetEvent(type="workflow.started", workflow_id=body.workflow_id))
    elif body.kind == "step.started":
        app_state.bus.emit(FleetEvent(type="workflow.phase.started", workflow_id=body.workflow_id, phase=body.payload.get("step")))
    elif body.kind == "step.completed":
        app_state.bus.emit(FleetEvent(type="workflow.phase.completed", workflow_id=body.workflow_id, phase=body.payload.get("step"), durationMs=body.payload.get("duration_ms", 0)))
    elif body.kind == "validator.blocked":
        compose_validator_exception(
            app_state.store,
            body.workflow_id,
            body.payload.get("validator", "unknown"),
            body.payload.get("reason", "validation failed"),
        )
        app_state.bus.emit(FleetEvent(type="workflow.exception.detected", workflow_id=body.workflow_id, category="validator-blocked", severity="high"))
    elif body.kind == "suspended":
        compose_hitl_exception(
            app_state.store,
            body.workflow_id,
            body.payload.get("reason", "approval"),
        )
        app_state.bus.emit(FleetEvent(type="workflow.hitl.requested", workflow_id=body.workflow_id, reason=body.payload.get("reason", "approval")))
    elif body.kind == "workflow.completed":
        app_state.bus.emit(FleetEvent(type="workflow.resolved", workflow_id=body.workflow_id, resolution="completed"))
    elif body.kind == "workflow.rejected":
        app_state.bus.emit(FleetEvent(
            type="workflow.resolved", workflow_id=body.workflow_id, resolution="rejected"
        ))
        w = app_state.store.get_workflow(body.workflow_id)
        if w:
            w.status = "failed"
            w.current_phase = "Approval"
    return {"received": True}
