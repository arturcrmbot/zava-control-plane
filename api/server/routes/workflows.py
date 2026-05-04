from __future__ import annotations
import time
from fastapi import APIRouter, HTTPException
from api.server.state import app_state
from api.server.services import economics, exception_narrative
from api.shared.types import Workflow

router = APIRouter(prefix="/api/workflows")


# Fleet/composed domains that the simulator spawns into Durable but does not
# currently upsert into app_state.store (state lives only in Durable + the
# FleetEvent stream). Mapping lets the detail endpoint synthesize a minimal
# Workflow record so the UI can still render a useful page.
_FLEET_PREFIX_TO_TYPE: dict[str, str] = {
    "TRV":  "travel-preapproval",
    "VKY":  "vendor-kyc",
    "ONB":  "employee-onboarding",
    "ITAR": "it-access-request",
    "CRN":  "contract-renewal",
    "PRR":  "perf-review",
}


def _synthesize_workflow(workflow_id: str) -> Workflow | None:
    """Build a minimal Workflow stub for a fleet/composed domain workflow that
    isn't in the store. Used by the detail endpoint so clicking through from
    the exception queue or dashboard shows a usable page instead of 404."""
    prefix = workflow_id.split("-", 1)[0]
    wf_type = _FLEET_PREFIX_TO_TYPE.get(prefix)
    if wf_type is None:
        return None
    excs = [
        e for e in app_state.store.list_exceptions(include_resolved=True)
        if e.workflow_id == workflow_id
    ]
    open_exc = next((e for e in excs if not e.resolved_at), None)
    created_at = min((e.created_at for e in excs), default=time.time())
    return Workflow(
        id=workflow_id,
        type=wf_type,  # type: ignore[arg-type]
        status="awaiting_hitl" if open_exc else "in_progress",
        current_phase="Intake",
        created_at=created_at,
        sla_due_at=created_at + 7 * 86400,  # nominal 7d SLA
        jurisdiction="London-WPP",
        agency="WPP",
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
    }
