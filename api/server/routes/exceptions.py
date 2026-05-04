from __future__ import annotations
import time
from typing import Literal
from fastapi import APIRouter, HTTPException
from api.server.state import app_state
from api.server.services import pending_gates
from api.shared import domains as _registry
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
@router.get("/", include_in_schema=False)
async def list_exceptions(include_resolved: bool = False):
    return [e.model_dump(by_alias=True) for e in app_state.store.list_exceptions(include_resolved=include_resolved)]


async def _resolve_one(exception_id: str, resolution: Resolution, resolved_by: str) -> bool:
    """Resolve a single exception, advancing the workflow's HITL gate when wired.

    Reads the per-workflow pending-gate cache (populated by
    api/server/routes/internal_durable_event.py on every `suspended` event)
    to find the right Durable external_event name. Falls back to the
    domain registry's resolve_external_event by (workflow_type,
    current_phase) if the cache is cold (e.g. FastAPI restart between
    suspend and operator click).

    Returns True if the exception was found and resolved (regardless of
    whether the orchestration event was raised — best-effort there).
    """
    exc = app_state.store.get_exception(exception_id)
    if not exc:
        return False
    app_state.store.resolve_exception(exception_id, resolved_by)
    w = app_state.store.get_workflow(exc.workflow_id)
    if not w:
        return True
    if w.status != "awaiting_hitl":
        return True
    w.status = "in_progress"
    w.action_ledger.append(ActionLedgerEntry(
        workflow_id=w.id, timestamp=time.time(),
        actor_kind="human", actor_id=resolved_by,
        action=f"reviewer.decision:{resolution}",
        revocable=False, details={"exception_id": exception_id},
    ))
    if not w.orchestration_instance_id:
        return True

    # Cache → registry fallback for the external_event name.
    gate = pending_gates.get(w.id)
    event_name: str | None = None
    payload: dict = {"decision": resolution, "resolved_by": resolved_by}
    if gate:
        event_name = gate.get("external_event")
    if event_name is None:
        event_name = _registry.resolve_external_event(w.type, w.current_phase)
    if event_name is None:
        # Legacy POC1 expense fallbacks for `Notify` / `Arbitrate` —
        # registry covers these but the Notify gate still needs a `text`
        # field on the payload (the existing claim_submitter contract).
        phase = w.current_phase
        if phase == "Notify":
            event_name = "justification"
            payload["text"] = "Reviewer-side override accepted via Control Plane."

    if event_name:
        from api.server.services.durable_client import raise_orchestration_event
        try:
            await raise_orchestration_event(
                w.orchestration_instance_id, event_name, payload,
            )
        except Exception as ex:
            print(f"[exceptions] failed to raise {event_name} for {w.id}: {ex}")
    else:
        print(
            f"[exceptions] no external_event registered for "
            f"workflow_type={w.type} phase={w.current_phase!r}; "
            f"orchestration {w.orchestration_instance_id} stays parked"
        )
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
