"""Phase 1 (Employee Lookup) graph for Travel pre-approval.

  deterministic_employee_lookup -> terminal

Per brief: read the employee's grade + cost-centre from Workday HR. Pass
forward. No agent, no validator — just a deterministic call that produces
the canonical phase output shape.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.server.mcp_tools.workday_hr_employee import get_employee


async def _employee_lookup_execute(input: dict) -> dict:
    """Deterministic employee lookup. Reads `trip.employee_id` from the
    orchestrator payload, calls the workday_hr_employee MCP tool directly
    (no agent session — pure I/O), returns the structured record."""
    trip = input.get("trip") or {}
    employee_id = trip.get("employee_id")
    if not employee_id:
        return {"ok": False, "blocked_reason": "missing trip.employee_id"}
    record = get_employee(employee_id)
    return {
        "ok": True,
        "employee_id": record["employee_id"],
        "grade": record["grade"],
        "cost_centre": record["cost_centre"],
        "agency": record["agency"],
        "home_market": record["home_market"],
        "manager_id": record["manager_id"],
    }


def build_fleet_travel_preapproval_employee_lookup_workflow() -> Workflow:
    return build_linear_workflow([
        ("employee_lookup", "deterministic_employee_lookup", "deterministic", _employee_lookup_execute),
    ])
