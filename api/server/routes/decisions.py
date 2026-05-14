"""Decision-investigation endpoints (pitch-i7).

`POST /api/decisions/replay/{id}` re-runs the persona's decision policy
against the CURRENT sandbox state and reports whether the same verdict
would still be reached today. This is a READ-ONLY investigation tool —
it does NOT mutate the original Decision node and does NOT emit any
bus events. Demonstrates "the org has changed its mind".
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from api.server.services.persona_responder import PERSONA_DEFINITIONS
from api.server.state import app_state


router = APIRouter(prefix="/api/decisions", tags=["decisions"])


def _parse_attributes(raw: Any) -> dict[str, Any]:
    """Decision.attributes is a JSON string column — coerce to dict."""
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _explanation_hints(
    *, persona_role: str, phase: str, decision_node: dict[str, Any]
) -> list[str]:
    """Surface anything that looks DIFFERENT about the inputs vs. the
    moment the original decision was made. Each lookup is best-effort —
    a missing module is fine, just skip the hint.
    """
    hints: list[str] = []

    # 1. Precedent count for the (persona_role, phase) tuple.
    try:
        from api.server.mcp_tools.query_precedents import (
            make_query_precedents_tool,
        )
        tool = make_query_precedents_tool(app_state.entities)
        prior = tool(persona_role, decision_node.get("workflow_id") or "", 50, phase=phase)
        if prior:
            hints.append(
                f"{len(prior)} prior decision(s) on file for "
                f"{persona_role}/{phase} since the original ruling"
            )
    except Exception:
        pass

    # 2. Vendor auto-block status (i2).
    try:
        from api.server.services.ambient_agents.vendor_block_watcher import (  # type: ignore
            is_vendor_auto_blocked,
        )
        attrs = _parse_attributes(decision_node.get("attributes"))
        vendor_id = (
            attrs.get("vendor_id")
            or attrs.get("vendor")
            or attrs.get("supplier_id")
        )
        if vendor_id and is_vendor_auto_blocked(vendor_id):
            hints.append(
                f"vendor {vendor_id!r} is now auto-blocked (was not at decision time)"
            )
    except Exception:
        pass

    # 3. Persona OOO today (d2 authority matrix).
    try:
        from api.shared.authority import is_ooo
        if is_ooo(persona_role):
            hints.append(f"{persona_role} is marked OOO today (ooo_today=True)")
    except Exception:
        pass

    # 4. Routing-stats hit-rate change (i4).
    try:
        from api.server.services import routing_stats  # type: ignore
        snap = routing_stats.snapshot(persona_role)  # type: ignore[attr-defined]
        if snap:
            hints.append(f"routing stats now report {snap}")
    except Exception:
        pass

    return hints


@router.post("/replay/{id}")
async def replay_decision(id: str) -> dict[str, Any]:
    """Re-run the persona's policy against CURRENT state and report
    whether it would still decide the same way. Read-only.
    """
    node = app_state.entities.get(id)
    if node is None or node.get("_label") != "Decision":
        raise HTTPException(status_code=404, detail=f"decision {id!r} not found")

    persona_role = node.get("persona_role") or ""
    phase = node.get("phase") or ""
    workflow_id = node.get("workflow_id") or ""

    persona = PERSONA_DEFINITIONS.get(persona_role)
    if persona is None:
        raise HTTPException(
            status_code=404,
            detail=f"persona {persona_role!r} no longer registered",
        )

    # Reconstruct the original context from the Decision attributes blob,
    # then layer the workflow's CURRENT payload on top so the replay sees
    # any policy / fixture / state changes that have landed since.
    attrs = _parse_attributes(node.get("attributes"))
    context: dict[str, Any] = dict(attrs.get("context") or attrs)
    context.setdefault("workflow_id", workflow_id)
    context.setdefault("phase", phase)
    context.setdefault("persona_role", persona_role)

    if workflow_id:
        try:
            wf = app_state.store.get_workflow(workflow_id)
        except Exception:
            wf = None
        if wf is not None and isinstance(getattr(wf, "payload", None), dict):
            for k, v in wf.payload.items():
                context[k] = v

    try:
        replay_payload = persona.decide(dict(context))
    except Exception as ex:  # pragma: no cover — defensive
        raise HTTPException(
            status_code=500, detail=f"persona policy crashed during replay: {ex}"
        )

    original_verdict = node.get("verdict") or ""
    original_reason = node.get("reason") or ""
    replay_verdict = str(replay_payload.get("decision") or "")
    replay_reason = str(replay_payload.get("reason") or "")

    changed_mind = replay_verdict != original_verdict
    hints = _explanation_hints(
        persona_role=persona_role, phase=phase, decision_node=node
    ) if changed_mind else []

    return {
        "decision_id": id,
        "original": {"verdict": original_verdict, "reason": original_reason},
        "replay": {"verdict": replay_verdict, "reason": replay_reason},
        "changed_mind": changed_mind,
        "explanation_hints": hints,
    }
