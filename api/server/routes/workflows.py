from __future__ import annotations
import time
from fastapi import APIRouter, HTTPException
from api.server.state import app_state
from api.server.services import economics, exception_narrative
from api.shared.types import Workflow
from api.shared import domains as _registry

router = APIRouter(prefix="/api/workflows")


def _synthesize_workflow(workflow_id: str) -> Workflow | None:
    """Last-resort stub for a workflow that isn't in the store.

    Phase 2 of feature-fleet-domain-substrate-1 made every spawner upsert
    into app_state.store, so this path should rarely fire. Kept as a
    defensive fallback for workflows that arrive via webhook before the
    spawn path runs (e.g. recorded blueprint replays). Resolves the
    workflow_type via the domain registry by workflow_id prefix.
    """
    domain = _registry.by_prefix(workflow_id)
    if domain is None:
        return None
    excs = [
        e for e in app_state.store.list_exceptions(include_resolved=True)
        if e.workflow_id == workflow_id
    ]
    open_exc = next((e for e in excs if not e.resolved_at), None)
    created_at = min((e.created_at for e in excs), default=time.time())
    return Workflow(
        id=workflow_id,
        type=domain.workflow_type,
        status="awaiting_hitl" if open_exc else "in_progress",
        current_phase="Intake",
        created_at=created_at,
        sla_due_at=created_at + 7 * 86400,
        jurisdiction="London-Zava",
        agency="Zava",
        active_exception_id=open_exc.id if open_exc else None,
    )


@router.get("")
@router.get("/", include_in_schema=False)
async def list_workflows(status: str | None = None, phase: str | None = None,
                         agency: str | None = None, has_exception: bool | None = None):
    items = app_state.store.list_workflows(status=status, phase=phase, agency=agency, has_exception=has_exception)
    return [w.model_dump(by_alias=True) for w in items]  # camelCase for UI


@router.get("/{id}")
async def get_workflow(id: str):
    w = app_state.store.get_workflow(id)
    if not w:
        w = _synthesize_workflow(id)
        if not w:
            raise HTTPException(404)
    active = (
        app_state.store.get_exception(w.active_exception_id)
        if w.active_exception_id else None
    )
    spans = app_state.store.get_spans(id)
    mcp_calls = app_state.store.get_mcp_calls(id)
    eco = economics.compute(w, spans=spans, mcp_calls=mcp_calls)
    narrative = (
        exception_narrative.compose(w, active, w.action_ledger)
        if active else None
    )
    return {
        "workflow": w.model_dump(by_alias=True),
        "phases": [p.model_dump(by_alias=True) for p in app_state.store.get_phases(id)],
        "spans": [s.model_dump(by_alias=True) for s in spans],
        "amplifications": [a.model_dump(by_alias=True) for a in app_state.store.get_amplifications(id)],
        "activeException": active.model_dump(by_alias=True) if active else None,
        "mcpCalls": [c.model_dump(by_alias=True) for c in mcp_calls],
        "economics": eco,
        "narrative": narrative,
        # Live append-blob URL for AC #12 immutable audit. None when the
        # cloud audit path isn't configured (CI / unit tests).
        "auditBlobUrl": app_state.audit.blob_url_for(id),
    }
