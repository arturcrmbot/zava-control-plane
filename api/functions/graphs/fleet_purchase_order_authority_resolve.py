"""Phase 3 (Authority Resolve) graph for Purchase Order domain.

  deterministic_authority_resolve -> terminal

Calls the delegated_authority MCP for action='purchase_order_approval' with
the PO's value+category, returns {approver_role, rule_id, threshold_gbp,
escalation_chain, basis} the orchestrator stamps onto the suspended
payload's persona field.

This is the pattern that makes one HITL gate dynamically route to
line_manager / category_manager / sourcing_lead / cpo depending on the
matrix's matched rule — no hard-coded persona chain in the orchestrator.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.server.mcp_tools.delegated_authority import resolve_approver


async def _authority_resolve_execute(input: dict) -> dict:
    po = input.get("purchase_order") or {}
    lookup = input.get("po_lookup") or {}
    amount = lookup.get("amount_gbp") or po.get("amount_gbp") or 0
    category = lookup.get("category") or po.get("category", "standard")
    try:
        result = resolve_approver(
            action="purchase_order_approval",
            value=float(amount) if amount else 0.0,
            category=category,
        )
        d = result.model_dump()
    except Exception as ex:
        return {
            "ok": False,
            "blocked_reason": f"authority MCP unreachable: {ex}",
            "approver_role": "category_manager",  # safe default
        }
    return {
        "ok": True,
        "approver_role": d.get("approver_role") or "category_manager",
        "rule_id": d.get("rule_id"),
        "threshold_gbp": d.get("threshold_gbp"),
        "escalation_chain": d.get("escalation_chain") or [],
        "basis": d.get("basis"),
        "matched": d.get("matched", False),
    }


def build_fleet_purchase_order_authority_resolve_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="authority_resolve",
        name="deterministic_authority_resolve",
        executor_type="deterministic",
        fn=_authority_resolve_execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )
