from __future__ import annotations
import time
from fastapi import APIRouter
from pydantic import BaseModel
from src.server.state import app_state
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
        app_state.bus.emit(FleetEvent(type="workflow.exception.detected", workflow_id=body.workflow_id, category="validator-blocked", severity="high"))
    elif body.kind == "suspended":
        app_state.bus.emit(FleetEvent(type="workflow.hitl.requested", workflow_id=body.workflow_id, reason=body.payload.get("reason", "approval")))
    elif body.kind == "workflow.completed":
        app_state.bus.emit(FleetEvent(type="workflow.resolved", workflow_id=body.workflow_id, resolution="completed"))
    return {"received": True}
