"""Phase 3 (Authority Resolve) graph for Treasury FX domain."""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.server.mcp_tools.delegated_authority import resolve_approver


async def _authority_resolve_execute(input: dict) -> dict:
    pos = input.get("position_check") or {}
    op_lookup = input.get("op_lookup") or {}
    op = input.get("treasury_op") or {}
    notional = pos.get("notional_gbp") or op_lookup.get("notional_gbp") or op.get("notional_gbp", 0)
    try:
        result = resolve_approver(
            action="treasury_fx_hedge",
            value=float(notional) if notional else 0.0,
            category="standard",
        )
        d = result.model_dump()
    except Exception as ex:
        return {
            "ok": False,
            "blocked_reason": f"authority MCP unreachable: {ex}",
            "approver_role": "treasurer",
        }
    return {
        "ok": True,
        "approver_role": d.get("approver_role") or "treasurer",
        "rule_id": d.get("rule_id"),
        "threshold_gbp": d.get("threshold_gbp"),
        "escalation_chain": d.get("escalation_chain") or [],
        "basis": d.get("basis"),
        "matched": d.get("matched", False),
    }


def build_fleet_treasury_fx_authority_resolve_workflow() -> Workflow:
    return build_linear_workflow([
        ("authority_resolve", "deterministic_authority_resolve", "deterministic", _authority_resolve_execute),
    ])
