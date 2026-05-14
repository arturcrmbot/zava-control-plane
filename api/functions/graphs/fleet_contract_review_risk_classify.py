"""Phase 2 (Risk Classify) graph for Contract Review domain.

  deterministic_risk_classify -> validator -> terminal

Reads the contract record + intake output, derives a category for the
matrix lookup. Categories used by the matrix:
  - 'nda'           — NDAs (CONTRACT-REVIEW-001)
  - 'msa'           — MSAs ≤£250k (CONTRACT-REVIEW-002)
  - 'msa' (>£250k)  — material MSAs (CONTRACT-REVIEW-003)
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.validators import validate_fleet_contract_review_risk_classify_schema


async def _risk_classify_execute(input: dict) -> dict:
    cr = input.get("contract_review") or {}
    intake = input.get("contract_intake") or {}
    contract_type = intake.get("contract_type") or cr.get("contract_type", "msa")
    deviates = bool(intake.get("deviates_from_template", cr.get("deviates_from_template", False)))
    amount = intake.get("amount_gbp") or cr.get("amount_gbp", 0)
    flags = []
    if deviates:
        flags.append("template-deviation")
    if contract_type == "msa" and amount > 250000:
        flags.append("material-msa")
    return {
        "ok": True,
        "contract_type": contract_type,
        "amount_gbp": amount,
        "deviates_from_template": deviates,
        "category": contract_type,  # matrix uses contract_type as category
        "flags": flags,
    }


def build_fleet_contract_review_risk_classify_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="risk_classify",
        name="deterministic_risk_classify",
        executor_type="deterministic",
        fn=_risk_classify_execute,
    )
    n2 = TrackedExecutor(
        id="val_risk_classify",
        name="validate_risk_classify_schema",
        executor_type="validator",
        fn=validate_fleet_contract_review_risk_classify_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
