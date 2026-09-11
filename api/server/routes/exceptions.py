from __future__ import annotations
import time
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from api.server.state import app_state
from api.server.services import pending_gates
from api.server.services.read_route_auth import Actor, require_actor
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
    resolved_by: str = "reviewer@zava"


@router.get("")
@router.get("/", include_in_schema=False)
async def list_exceptions(include_resolved: bool = False):
    """Operator queue. Returns one row per workflow that's currently
    awaiting human review, deduplicated on workflow_id.

    Two issues this filter solves:
    1. fleet_manager_service augments exceptions asynchronously and
       creates a NEW exception entry (composedBy=fleet-manager,
       fleet-manager-augmented) instead of updating the existing
       deterministic one. Without dedup, the queue shows 2-3 rows for
       a single suspend.
    2. Async-created exceptions can land AFTER the workflow has already
       resumed past the HITL gate (race: persona-responder closes the
       gate before fleet-manager augments the exception). _auto_resolve_open
       only catches exceptions that exist at resume time, so post-resume
       additions stay open. Filtering by workflow.status='awaiting_hitl'
       hides them so the queue only ever shows actionable items.

    `include_resolved=true` bypasses both filters and returns the raw
    list — useful for admin / audit views.
    """
    raw = app_state.store.list_exceptions(include_resolved=include_resolved)
    if include_resolved:
        return [e.model_dump(by_alias=True) for e in raw]

    # Build a workflow_id -> status map so we can drop exceptions whose
    # workflow has already moved on.
    status_by_wid = {w.id: w.status for w in app_state.store.list_workflows()}
    visible = [e for e in raw if status_by_wid.get(e.workflow_id) == "awaiting_hitl"]

    # Dedup per workflow: prefer fleet-manager-augmented (richest summary
    # + recommendation), then fleet-manager, then deterministic.
    rank = {"fleet-manager-augmented": 0, "fleet-manager": 1, "deterministic": 2}
    by_wid: dict[str, object] = {}
    for e in visible:
        prev = by_wid.get(e.workflow_id)
        if prev is None or rank.get(e.composed_by, 99) < rank.get(prev.composed_by, 99):
            by_wid[e.workflow_id] = e
    return [e.model_dump(by_alias=True) for e in by_wid.values()]


async def _resolve_one(
    exception_id: str,
    resolution: Resolution,
    resolved_by: str,
    actor: Actor | None = None,
) -> bool:
    """Resolve a single exception, advancing the workflow's HITL gate when wired.

    Reads the per-workflow pending-gate cache (populated by
    api/server/routes/internal_durable_event.py on every `suspended` event)
    to find the right Durable external_event name. Falls back to the
    domain registry's resolve_external_event by (workflow_type,
    current_phase) if the cache is cold (e.g. FastAPI restart between
    suspend and operator click).

    Returns True if the exception was found and resolved. For a suspended
    Durable workflow, resolution is committed only after the external event
    has been delivered.
    """
    exc = app_state.store.get_exception(exception_id)
    if not exc:
        return False
    if exc.resolved_at is not None:
        w = app_state.store.get_workflow(exc.workflow_id)
        if w is not None and w.type == "aurora-budget-response":
            raise HTTPException(409, f"decision {exception_id} already resolved")
        return True
    w = app_state.store.get_workflow(exc.workflow_id)
    if not w:
        app_state.store.resolve_exception(exception_id, resolved_by)
        return True
    if w.status != "awaiting_hitl":
        if w.type == "aurora-budget-response":
            raise HTTPException(409, f"workflow {w.id} is not awaiting a decision")
        app_state.store.resolve_exception(exception_id, resolved_by)
        return True

    # Cache → registry fallback for the external_event name.
    gate = pending_gates.get(w.id)
    event_name: str | None = None
    payload: dict = {"decision": resolution, "resolved_by": resolved_by}
    if gate:
        event_name = gate.get("external_event")
    if event_name is None:
        event_name = _registry.resolve_external_event(w.type, w.current_phase)
    domain = _registry.DOMAINS.get(w.type)
    if domain is not None:
        authority_gate = next(
            (
                candidate
                for candidate in domain.hitl_gates
                if candidate.gate_phase == w.current_phase
                or candidate.external_event == event_name
            ),
            None,
        )
        if authority_gate is not None:
            payload["persona"] = authority_gate.persona
            payload["decision_id"] = exception_id
    hitl_context = (
        w.payload.get("hitl_context")
        if isinstance(w.payload, dict)
        else None
    )
    if isinstance(hitl_context, dict):
        for key in (
            "workflow_id",
            "story_id",
            "selected_option_id",
            "decision_id",
            "evidence_versions",
        ):
            if key in hitl_context:
                payload[key] = hitl_context[key]
    if w.type == "aurora-budget-response":
        if actor is None:
            raise HTTPException(401, "authenticated actor required for Aurora decision")
        if resolution not in {"approve", "reject"}:
            raise HTTPException(
                400,
                "Aurora operator gate accepts only approve or reject",
            )
        proposed_action = (
            hitl_context.get("proposed_action")
            if isinstance(hitl_context, dict)
            else None
        )
        proposed_action = (
            proposed_action if isinstance(proposed_action, dict) else {}
        )
        attributes = dict(proposed_action.get("attributes") or {})
        action = str(proposed_action.get("kind") or "")
        category = str(attributes.get("scope") or "")
        from api.server.services.governance import kernel

        authority = kernel().check_authority(
            role=actor.role,
            action=action,
            category=category,
            requester_role=actor.role,
        )
        if not authority.allowed:
            raise HTTPException(403, authority.reason)
        resolved_by = actor.id
        payload["resolved_by"] = actor.id
        payload["actor_role"] = actor.role
        payload["governing_rule_id"] = authority.governing_rule_id
        payload["proposed_action"] = proposed_action
    if event_name is None:
        # Legacy POC1 expense fallbacks for `Notify` / `Arbitrate` —
        # registry covers these but the Notify gate still needs a `text`
        # field on the payload (the existing claim_submitter contract).
        phase = w.current_phase
        if phase == "Notify":
            event_name = "justification"
            payload["text"] = "Reviewer-side override accepted via Control Plane."

    if event_name and w.orchestration_instance_id:
        from api.server.services.durable_client import raise_orchestration_event
        try:
            delivered = await raise_orchestration_event(
                w.orchestration_instance_id, event_name, payload,
            )
        except Exception as ex:
            raise HTTPException(
                503,
                f"Durable event delivery failed for workflow {w.id}",
            ) from ex
        if delivered is False:
            raise HTTPException(
                503,
                f"Durable instance unavailable for workflow {w.id}",
            )
    elif w.orchestration_instance_id:
        raise HTTPException(
            503,
            f"No external event registered for workflow {w.id}",
        )

    app_state.store.resolve_exception(exception_id, resolved_by)
    w.status = "in_progress"
    if w.type == "aurora-budget-response":
        w.payload = dict(w.payload or {})
        decisions = list(w.payload.get("decisions") or [])
        decisions.append({
            "decision_id": exception_id,
            "phase": w.current_phase,
            "persona_role": actor.role if actor is not None else "unknown",
            "verdict": resolution,
            "reason": payload.get("reason"),
            "resolved_by": resolved_by,
            "source_event": event_name,
            "governing_rule_id": payload.get("governing_rule_id"),
        })
        w.payload["decisions"] = decisions
        app_state.store.upsert_workflow(w)
    w.action_ledger.append(ActionLedgerEntry(
        workflow_id=w.id, timestamp=time.time(),
        actor_kind="human", actor_id=resolved_by,
        action=f"reviewer.decision:{resolution}",
        revocable=False, details={"exception_id": exception_id},
    ))
    return True


@router.post("/{exception_id}/resolve")
async def resolve_one(
    exception_id: str,
    body: ResolveBody,
    actor: Actor = Depends(require_actor),
):
    ok = await _resolve_one(
        exception_id,
        body.resolution,
        body.resolved_by,
        actor=actor,
    )
    if not ok:
        raise HTTPException(404, f"exception {exception_id} not found")
    return {"resolved": 1, "exception_id": exception_id, "resolution": body.resolution}


@router.post("/bulk-resolve")
async def bulk_resolve(
    body: BulkResolveBody,
    actor: Actor = Depends(require_actor),
):
    resolved = 0
    for id in body.exception_ids:
        if await _resolve_one(
            id,
            body.resolution,
            body.resolved_by,
            actor=actor,
        ):
            resolved += 1
    return {"resolved": resolved}
