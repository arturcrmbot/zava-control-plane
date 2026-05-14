"""HTTP read surface for persona insights.

Closed-loop autonomous-domain-insights. Three GET endpoints:

  GET  /api/personas/{role}/insights/latest          (per-role)
  GET  /api/personas/insights/latest                 (cross-role / CEO synth)
  GET  /api/personas/labels/preview                  (plain-language labels)

Persona policy proposals **self-apply** in
:mod:`api.server.services.policy_application` — gated only by the AGT
matrix, never by an operator click. There is intentionally no approve
route here.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from api.server.state import app_state
from api.server.services.read_route_auth import Actor, require_actor
from api.server.services.plain_language import pretty_action, pretty_decision

router = APIRouter(prefix="/api/personas")


@router.get("/labels/preview")
async def labels_preview(
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Returns a small dictionary of plain-language labels for known
    verdicts / scopes / persona roles. Used by the UI to render
    buyer-comprehensible strings without duplicating the mapping client-side.
    """
    from api.server.services.plain_language import (
        _VERDICT_LABEL, _SCOPE_LABEL, _PERSONA_TITLE,
    )
    return {
        "verdicts": dict(_VERDICT_LABEL),
        "scopes": dict(_SCOPE_LABEL),
        "personas": dict(_PERSONA_TITLE),
    }


def _row_to_insight(row: dict[str, Any]) -> dict[str, Any]:
    """Decode the JSON-encoded columns + ISO timestamps for the wire."""
    decided_at = row.get("decided_at")
    out = {
        "id": row.get("id"),
        "role": row.get("role"),
        "scope": row.get("scope"),
        "decided_at": decided_at.isoformat() if hasattr(decided_at, "isoformat") else decided_at,
        "headline": row.get("headline") or "",
        "body": row.get("body") or "",
        "fingerprint": row.get("fingerprint") or "",
    }
    for col in ("kpis", "proposed_actions"):
        raw = row.get(col)
        if raw:
            try:
                out[col] = json.loads(raw)
            except (TypeError, ValueError):
                out[col] = None
        else:
            out[col] = {} if col == "kpis" else []
    return out


@router.get("/insights/latest")
async def latest_per_role(
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Return one Insight per role (the most recent for each role).

    Used by the CEO synthesis surface and by any client that wants a
    cross-domain snapshot. Two-step Kuzu pattern (no window functions
    in 0.6.1): first compute (role, latest_decided_at) pairs, then
    re-MATCH to fetch the full row for each.
    """
    pairs = app_state.entities.query(
        "MATCH (i:Insight) "
        "WITH i.role AS role_, max(i.decided_at) AS latest "
        "RETURN role_, latest"
    )
    insights = []
    for p in pairs:
        rows = app_state.entities.query(
            "MATCH (i:Insight) WHERE i.role = $role AND i.decided_at = $ts "
            "RETURN i.id AS id, i.role AS role, i.scope AS scope, "
            "       i.decided_at AS decided_at, i.headline AS headline, "
            "       i.body AS body, i.kpis AS kpis, "
            "       i.proposed_actions AS proposed_actions, "
            "       i.fingerprint AS fingerprint LIMIT 1",
            {"role": p["role_"], "ts": p["latest"]},
        )
        if rows:
            insights.append(_row_to_insight(rows[0]))
    insights.sort(key=lambda d: d["role"])
    return {"insights": insights}


@router.get("/{role}/insights/latest")
async def latest_for_role(
    role: str = Path(..., min_length=1, max_length=64),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    rows = app_state.entities.query(
        "MATCH (i:Insight {role: $role}) "
        "RETURN i.id AS id, i.role AS role, i.scope AS scope, "
        "       i.decided_at AS decided_at, i.headline AS headline, "
        "       i.body AS body, i.kpis AS kpis, "
        "       i.proposed_actions AS proposed_actions, "
        "       i.fingerprint AS fingerprint "
        "ORDER BY i.decided_at DESC LIMIT 1",
        {"role": role},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"no insight for role {role!r}")
    return _row_to_insight(rows[0])
