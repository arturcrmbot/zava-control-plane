from __future__ import annotations
import time
from typing import Literal
from fastapi import APIRouter, HTTPException
from api.server.state import app_state
from api.shared.types import ActionLedgerEntry, BaseModel  # BaseModel here = camelCase-aliased

router = APIRouter(prefix="/api/exceptions")

Resolution = Literal[
    "approve", "reject", "escalate",
    "reroute-gl", "request-info",
]


class BulkResolveBody(BaseModel):
    exception_ids: list[str]
    resolution: Resolution
    resolved_by: str


class ResolveBody(BaseModel):
    resolution: Resolution
    resolved_by: str = "reviewer@wpp"


@router.get("")
async def list_exceptions(include_resolved: bool = False):
    return [e.model_dump(by_alias=True) for e in app_state.store.list_exceptions(include_resolved=include_resolved)]


async def _resolve_one(exception_id: str, resolution: Resolution, resolved_by: str) -> bool:
    """Resolve a single exception, advancing the workflow's HITL gate when wired.

    Handles both invoice (phase=Approval) and expense (phase=Notify or
    Arbitrate) HITL gates by sending the appropriate orchestration event.
    Returns True if the exception was found and resolved.
    """
    exc = app_state.store.get_exception(exception_id)
    if not exc:
        return False
    app_state.store.resolve_exception(exception_id, resolved_by)
    w = app_state.store.get_workflow(exc.workflow_id)
    if not w:
        return True
    if w.status == "awaiting_hitl":
        w.status = "in_progress"
        w.action_ledger.append(ActionLedgerEntry(
            workflow_id=w.id, timestamp=time.time(),
            actor_kind="human", actor_id=resolved_by,
            action=f"reviewer.decision:{resolution}",
            revocable=False, details={"exception_id": exception_id},
        ))
        if w.orchestration_instance_id:
            from api.server.services.durable_client import raise_orchestration_event
            event_name = None
            payload: dict = {"decision": resolution, "resolved_by": resolved_by}
            phase = w.current_phase
            if phase == "Approval":
                event_name = "approval_decision"
            elif phase == "Notify":
                # claimant submitted justification; let orchestrator advance to Arbitrate
                event_name = "justification"
                payload["text"] = "Reviewer-side override accepted via Control Plane."
            elif phase == "Arbitrate":
                event_name = "reviewer_decision"
            if event_name:
                try:
                    await raise_orchestration_event(
                        w.orchestration_instance_id, event_name, payload,
                    )
                except Exception as ex:
                    print(f"[exceptions] failed to raise {event_name} for {w.id}: {ex}")
    return True


@router.post("/{exception_id}/resolve")
async def resolve_one(exception_id: str, body: ResolveBody):
    ok = await _resolve_one(exception_id, body.resolution, body.resolved_by)
    if not ok:
        raise HTTPException(404, f"exception {exception_id} not found")
    return {"resolved": 1, "exception_id": exception_id, "resolution": body.resolution}


@router.post("/bulk-resolve")
async def bulk_resolve(body: BulkResolveBody):
    resolved = 0
    for id in body.exception_ids:
        if await _resolve_one(id, body.resolution, body.resolved_by):
            resolved += 1
    return {"resolved": resolved}
