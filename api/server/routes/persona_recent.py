"""Per-persona recent activity surface — Phase 6 IP7 (TASK-040).

Backs ``GET /api/persona/{role}/recent`` for the Org Building zoom-1
"click a persona desk" sidebar. Returns the last N pending HITL gates
(from in-flight workflows' ``payload['gates']``) and the last N decisions
recorded for that persona role (from the entity-graph plane).

Both halves are best-effort: when the entity plane is disabled the
decisions list collapses to empty; pending gates are always derivable
from the in-process workflow store.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from api.server.state import app_state

router = APIRouter(prefix="/api/persona")


def _pending_gates_for(role: str, limit: int) -> list[dict[str, Any]]:
    """Walk in-flight workflows; collect any unresolved gates whose
    persona_role matches.

    Gate structure varies by domain (each composer plants its own
    shape) — we look at ``payload['gates']`` first and extract the
    common keys (``id``, ``persona_role``, ``status``, ``opened_at``).
    Anything unresolved + role-matching counts.
    """
    out: list[dict[str, Any]] = []
    workflows = app_state.store.list_workflows()
    for wf in workflows:
        gates = (wf.payload or {}).get("gates") or []
        if not isinstance(gates, list):
            continue
        for gate in gates:
            if not isinstance(gate, dict):
                continue
            if gate.get("persona_role") != role:
                continue
            status = gate.get("status") or gate.get("state")
            if status in ("resolved", "approved", "rejected", "auto_closed"):
                continue
            out.append(
                {
                    "workflow_id": wf.id,
                    "workflow_type": wf.type,
                    "gate_id": gate.get("id") or gate.get("gate_id"),
                    "name": gate.get("name") or gate.get("kind"),
                    "persona_role": role,
                    "opened_at": gate.get("opened_at") or gate.get("created_at"),
                    "status": status or "pending",
                }
            )
    out.sort(key=lambda g: g.get("opened_at") or 0, reverse=True)
    return out[:limit]


def _recent_decisions_for(role: str, limit: int) -> list[dict[str, Any]]:
    """Pull the last ``limit`` Decision nodes whose ``persona_role`` matches.

    Returns ``[]`` when the entity plane is disabled (``app_state.entities``
    not wired) — keeps the endpoint usable in CI / minimal deployments.
    """
    entities = getattr(app_state, "entities", None)
    if entities is None:
        return []
    try:
        rows = entities.query(
            "MATCH (d:Decision) WHERE d.persona_role = $pr "
            "RETURN d ORDER BY d.decided_at DESC "
            f"LIMIT {int(limit)}",
            {"pr": role},
        )
    except Exception:  # pragma: no cover — defensive
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        d = row.get("d") or {}
        out.append(
            {
                "decision_id": d.get("id") or d.get("decision_id"),
                "workflow_id": d.get("workflow_id"),
                "persona_role": d.get("persona_role") or role,
                "verdict": d.get("verdict"),
                "reason": d.get("reason"),
                "decided_at": d.get("decided_at"),
            }
        )
    return out


@router.get("/{role}/recent")
def persona_recent(role: str, limit: int = 10) -> dict[str, Any]:
    """Pending HITL gates + recent decisions for one persona role.

    Both lists are capped at ``limit`` (default 10). 422-equivalent on
    invalid limits is delegated to FastAPI/Pydantic; we hard-floor at 1.
    """
    if not role:
        raise HTTPException(status_code=400, detail="role required")
    n = max(1, min(100, int(limit)))
    return {
        "role": role,
        "pending_gates": _pending_gates_for(role, n),
        "recent_decisions": _recent_decisions_for(role, n),
    }
