"""Phase 1 (Transfer Intake) graph for Employee transfer between organisations.

  deterministic_transfer_intake -> terminal

Per brief: capture the proposed transfer (employee_id, source_org_id,
target_org_id, effective_date, target_role, business_reason). Pass forward.
No agent, no validator — just a deterministic pass-through that produces
the canonical phase output shape.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow


async def _transfer_intake_execute(input: dict) -> dict:
    """Deterministic transfer intake. Reads the proposed transfer fields
    from the orchestrator payload and stamps a canonical output shape."""
    transfer = input.get("transfer") or input.get("payload") or {}
    employee_id = transfer.get("employee_id") or input.get("employee_id")
    source_org_id = transfer.get("source_org_id") or input.get("source_org_id")
    target_org_id = transfer.get("target_org_id") or input.get("target_org_id")
    effective_date = transfer.get("effective_date") or input.get("effective_date")
    target_role = transfer.get("target_role") or input.get("target_role")
    business_reason = (
        transfer.get("business_reason") or input.get("business_reason") or ""
    )
    if not employee_id or not source_org_id or not target_org_id:
        return {
            "ok": False,
            "blocked_reason": "missing employee_id / source_org_id / target_org_id",
        }
    return {
        "ok": True,
        "employee_id": employee_id,
        "source_org_id": source_org_id,
        "target_org_id": target_org_id,
        "effective_date": effective_date,
        "target_role": target_role,
        "business_reason": business_reason,
    }


def build_fleet_employee_transfer_transfer_intake_workflow() -> Workflow:
    return build_linear_workflow([
        ("transfer_intake", "deterministic_transfer_intake", "deterministic", _transfer_intake_execute),
    ])
