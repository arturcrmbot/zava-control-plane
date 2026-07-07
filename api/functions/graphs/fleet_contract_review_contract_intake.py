"""Phase 1 (Contract Intake) graph for Contract Review domain."""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow


async def _contract_intake_execute(input: dict) -> dict:
    cr = input.get("contract_review") or {}
    contract_id = cr.get("contract_id")
    if not contract_id:
        return {"ok": False, "blocked_reason": "missing contract_review.contract_id"}
    return {
        "ok": True,
        "contract_id": contract_id,
        "vendor": cr.get("vendor_name"),
        "contract_type": cr.get("contract_type", "msa"),
        "amount_gbp": cr.get("amount_gbp", 0),
        "deviates_from_template": bool(cr.get("deviates_from_template", False)),
    }


def build_fleet_contract_review_contract_intake_workflow() -> Workflow:
    return build_linear_workflow([
        ("contract_intake", "deterministic_contract_intake", "deterministic", _contract_intake_execute),
    ])
