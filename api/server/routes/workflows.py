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


# ---------------------------------------------------------------------------
# Org Ops v2 — endpoints used by the live operator views (Control Room,
# Conversations, Workflow River). All three views share these.
# ---------------------------------------------------------------------------

def _function_for_workflow_type(workflow_type: str) -> str | None:
    """workflow_type -> function key (e.g. 'vendor-kyc' -> 'finance')."""
    try:
        from api.shared.functions import FUNCTIONS
    except Exception:
        return None
    for fn_key, fn_spec in FUNCTIONS.items():
        if workflow_type in (fn_spec.owns_domains or ()):
            return fn_key
    return None


def _last_actor(workflow) -> dict | None:
    """Best-effort summary of who/what last touched the workflow.

    Walks action_ledger tail (most recent first) and surfaces a small dict
    {kind: 'agent'|'tool'|'persona'|'system', name: str, at: float} so the
    operator views can show 'currently: ap_clerk thinking 4s' in the rail.
    """
    ledger = list(getattr(workflow, "action_ledger", None) or [])
    if not ledger:
        return None
    tail = ledger[-1]
    actor_id = getattr(tail, "actor_id", None) or "?"
    actor_kind = getattr(tail, "actor_kind", None) or "system"
    return {
        "kind": str(actor_kind),
        "name": str(actor_id),
        "at": float(getattr(tail, "timestamp", 0.0)),
    }


@router.get("/index/in-flight")
async def list_in_flight():
    """Every non-terminal workflow with phase, age, current actor, SLA position.

    Used by Approach A's left rail, Approach B's channel list, and Approach C's
    chip pool. Terminal statuses excluded: ``completed`` and ``failed``.
    """
    now = time.time()
    items = []
    for w in app_state.store.list_workflows():
        if w.status in {"completed", "failed"}:
            continue
        age_s = now - float(w.created_at or now)
        sla_due = float(w.sla_due_at or w.created_at + 7 * 86400)
        sla_total = max(1.0, sla_due - float(w.created_at or now))
        sla_pct = max(0.0, min(1.0, (now - float(w.created_at or now)) / sla_total))
        items.append({
            "id": w.id,
            "workflow_type": w.type,
            "function": _function_for_workflow_type(w.type),
            "status": w.status,
            "phase": w.current_phase,
            "created_at": w.created_at,
            "age_s": round(age_s, 2),
            "sla_pct": round(sla_pct, 3),
            "active_exception_id": w.active_exception_id,
            "last_actor": _last_actor(w),
        })
    items.sort(key=lambda r: (
        # awaiting_hitl first, then by age descending so the oldest unattended
        # workflow tops the list
        0 if r["status"] == "awaiting_hitl" else 1,
        -r["age_s"],
    ))
    return items


@router.get("/index/timeline/{id}")
async def workflow_timeline(id: str):
    """Chronological list of every event for a workflow with full payloads.

    Composed from: phases (deterministic per-phase rows), spans (skill/agent
    activity), mcp_calls (tool invocations), action_ledger (persona + system
    interventions), and decisions stashed on payload. Returns one flat list
    sorted by timestamp ascending so the operator drawer can render it as a
    transcript.
    """
    w = app_state.store.get_workflow(id)
    if not w:
        raise HTTPException(404)
    rows: list[dict] = []
    for p in app_state.store.get_phases(id):
        rows.append({
            "ts": float(getattr(p, "started_at", None) or w.created_at),
            "kind": "phase",
            "label": getattr(p, "name", "?"),
            "status": getattr(p, "status", "?"),
            "completed_at": getattr(p, "completed_at", None),
        })
    for s in app_state.store.get_spans(id):
        rows.append({
            "ts": float(getattr(s, "started_at", None) or w.created_at),
            "kind": "agent",
            "label": getattr(s, "skill", None) or getattr(s, "name", "?"),
            "status": getattr(s, "status", "ok"),
            "tokens": getattr(s, "tokens", None),
            "completed_at": getattr(s, "completed_at", None),
        })
    for c in app_state.store.get_mcp_calls(id):
        rows.append({
            "ts": float(getattr(c, "started_at", None) or w.created_at),
            "kind": "tool",
            "label": getattr(c, "tool", None) or "?",
            "status": getattr(c, "status", "ok"),
            "result_summary": getattr(c, "result_summary", None),
        })
    for entry in (w.action_ledger or []):
        rows.append({
            "ts": float(getattr(entry, "timestamp", None) or w.created_at),
            "kind": getattr(entry, "actor_kind", "system"),
            "label": getattr(entry, "action", "?"),
            "actor": getattr(entry, "actor_id", "?"),
            "details": getattr(entry, "details", None),
        })
    for d in (w.payload.get("decisions") if isinstance(w.payload, dict) else []) or []:
        ts = d.get("decided_at")
        try:
            import datetime as _dt
            ts_val = _dt.datetime.fromisoformat(ts).timestamp() if isinstance(ts, str) else float(ts or w.created_at)
        except Exception:
            ts_val = float(w.created_at)
        rows.append({
            "ts": ts_val,
            "kind": "decision",
            "label": d.get("phase"),
            "actor": d.get("persona_role"),
            "verdict": d.get("verdict"),
            "reason": d.get("reason"),
        })
    rows.sort(key=lambda r: r["ts"])
    return {
        "workflow": w.model_dump(by_alias=True),
        "timeline": rows,
    }
