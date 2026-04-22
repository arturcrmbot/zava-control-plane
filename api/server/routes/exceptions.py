from __future__ import annotations
import time
from typing import Literal
from fastapi import APIRouter
from api.server.state import app_state
from api.shared.types import ActionLedgerEntry, BaseModel  # BaseModel here = camelCase-aliased

router = APIRouter(prefix="/api/exceptions")


class BulkResolveBody(BaseModel):
    exception_ids: list[str]
    resolution: Literal[
        "approve", "reject", "escalate",
        "reroute-gl", "request-info",
    ]
    resolved_by: str


@router.get("/")
async def list_exceptions(include_resolved: bool = False):
    return [e.model_dump(by_alias=True) for e in app_state.store.list_exceptions(include_resolved=include_resolved)]


@router.post("/bulk-resolve")
async def bulk_resolve(body: BulkResolveBody):
    resolved = 0
    for id in body.exception_ids:
        exc = app_state.store.get_exception(id)
        if not exc:
            continue
        app_state.store.resolve_exception(id, body.resolved_by)
        w = app_state.store.get_workflow(exc.workflow_id)
        if w and w.status == "awaiting_hitl":
            w.status = "in_progress"
            w.action_ledger.append(ActionLedgerEntry(
                workflow_id=w.id, timestamp=time.time(),
                actor_kind="human", actor_id=body.resolved_by,
                action=f"bulk-resolve:{body.resolution}",
                revocable=False, details={"exception_id": id}
            ))
            # If this workflow is HITL-paused on the Approval step, signal the orchestration
            if w.orchestration_instance_id and w.current_phase == "Approval":
                from api.server.services.durable_client import raise_orchestration_event
                try:
                    await raise_orchestration_event(
                        w.orchestration_instance_id,
                        "approval_decision",
                        {"decision": body.resolution, "resolved_by": body.resolved_by},
                    )
                except Exception as ex:
                    print(f"[exceptions] failed to raise approval_decision for {w.id}: {ex}")
        resolved += 1
    return {"resolved": resolved}
