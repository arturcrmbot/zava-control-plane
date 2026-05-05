"""Phase 3 (Authority Resolve) graph for Contract Review domain."""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.server.mcp_tools.delegated_authority import resolve_approver


async def _authority_resolve_execute(input: dict) -> dict:
    risk = input.get("risk_classify") or {}
    intake = input.get("contract_intake") or {}
    cr = input.get("contract_review") or {}
    amount = risk.get("amount_gbp") or intake.get("amount_gbp") or cr.get("amount_gbp", 0)
    category = risk.get("category") or intake.get("contract_type") or "msa"
    try:
        result = resolve_approver(
            action="contract_review_signoff",
            value=float(amount) if amount else 0.0,
            category=category,
        )
        d = result.model_dump()
    except Exception as ex:
        return {
            "ok": False,
            "blocked_reason": f"authority MCP unreachable: {ex}",
            "approver_role": "contracts_counsel",
        }
    # Special-case: any template-deviation auto-escalates to GC regardless of
    # band. The persona's decision_policy honours this; surface it here so the
    # operator UI shows GC up-front rather than discovering it after the
    # persona escalates.
    deviates = bool(risk.get("deviates_from_template") or intake.get("deviates_from_template"))
    approver = d.get("approver_role") or "contracts_counsel"
    if deviates and approver == "contracts_counsel":
        approver = "gc"
    return {
        "ok": True,
        "approver_role": approver,
        "rule_id": d.get("rule_id"),
        "threshold_gbp": d.get("threshold_gbp"),
        "escalation_chain": d.get("escalation_chain") or [],
        "basis": d.get("basis"),
        "matched": d.get("matched", False),
        "promoted_for_deviation": deviates and (d.get("approver_role") == "contracts_counsel"),
    }


def build_fleet_contract_review_authority_resolve_workflow() -> Workflow:
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
