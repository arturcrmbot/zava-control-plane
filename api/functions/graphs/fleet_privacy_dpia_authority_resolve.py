"""Phase 3 (Authority Resolve) graph for Privacy DPIA domain."""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.server.mcp_tools.delegated_authority import resolve_approver


async def _authority_resolve_execute(input: dict) -> dict:
    risk = input.get("risk_classify") or {}
    intake = input.get("dpia_intake") or {}
    category = risk.get("category") or intake.get("risk_tier") or "low_risk"
    geography = risk.get("geography") or intake.get("geography") or "EMEA"
    try:
        result = resolve_approver(
            action="privacy_dpia_signoff",
            category=category,
            geography=geography,
        )
        d = result.model_dump()
    except Exception as ex:
        return {
            "ok": False,
            "blocked_reason": f"authority MCP unreachable: {ex}",
            "approver_role": "dpo",
        }
    return {
        "ok": True,
        "approver_role": d.get("approver_role") or "dpo",
        "rule_id": d.get("rule_id"),
        "threshold_gbp": d.get("threshold_gbp"),
        "escalation_chain": d.get("escalation_chain") or [],
        "basis": d.get("basis"),
        "matched": d.get("matched", False),
    }


def build_fleet_privacy_dpia_authority_resolve_workflow() -> Workflow:
    return build_linear_workflow([
        ("authority_resolve", "deterministic_authority_resolve", "deterministic", _authority_resolve_execute),
    ])
