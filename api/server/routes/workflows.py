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


@router.get("/{id}/tree")
async def get_workflow_tree(id: str, max_depth: int = 16):
    """Recursive sub-orchestrator tree (Phase 4 IP7 TASK-033, DEC-OQ5).

    Walks the ``Workflow -> Workflow`` self-relation
    (``SUB_WORKFLOW_OF`` rel table) starting from ``id`` and returns
    a JSON tree of ``{workflow_id, workflow_type, status, children: [...]}``.

    Leaf workflows (no SUB_WORKFLOW_OF rels) and ids unknown to the
    entity graph both surface a single-node tree with ``status="unknown"``
    — this is intentional: the entity graph only sees workflows that
    have been spawned via the meta-workflow path or otherwise written
    to the Workflow node table. Cycle protection short-circuits at
    ``max_depth`` and on any id revisit (defensive — graph should not
    contain cycles).
    """
    seen: set[str] = set()

    def _node(node_dict: dict | None, wid: str) -> dict:
        if node_dict is None:
            return {
                "workflow_id": wid,
                "workflow_type": None,
                "status": "unknown",
                "children": [],
            }
        return {
            "workflow_id": node_dict.get("id", wid),
            "workflow_type": node_dict.get("workflow_type"),
            "status": node_dict.get("status") or "unknown",
            "children": [],
        }

    def _walk(wid: str, depth: int) -> dict:
        if wid in seen or depth >= max_depth:
            return _node(app_state.entities.get(wid), wid)
        seen.add(wid)
        node = _node(app_state.entities.get(wid), wid)
        try:
            children = app_state.entities.linked(wid, rel="SUB_WORKFLOW_OF")
        except Exception:
            children = []
        for row in children:
            child = row.get("node") if isinstance(row, dict) else None
            child_id = child.get("id") if isinstance(child, dict) else None
            if not child_id:
                continue
            node["children"].append(_walk(child_id, depth + 1))
        return node

    return _walk(id, 0)
