"""Phase 1 (Employee Lookup) graph for IT access request.

  deterministic_employee_lookup -> terminal

Per brief: read the requester's grade, cost-centre, agency and home_market
from Workday HR. Pass forward. No agent, no validator — just a
deterministic call that produces the canonical phase output shape and
carries the request's business_justification + requested_role_templates
through so downstream phases (and the line-manager persona) can read
them from a single dict.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.server.mcp_tools.workday_hr_employee import get_employee


async def _employee_lookup_execute(input: dict) -> dict:
    """Deterministic employee lookup. Reads `request.employee_id` from the
    orchestrator payload, calls the workday_hr_employee MCP tool directly
    (no agent session — pure I/O), returns the structured record plus the
    request fields the downstream persona policy reads from `employee_lookup`."""
    request = input.get("request") or {}
    employee_id = request.get("employee_id")
    if not employee_id:
        return {"ok": False, "blocked_reason": "missing request.employee_id"}
    record = get_employee(employee_id)
    return {
        "ok": True,
        "employee_id": record["employee_id"],
        "grade": record["grade"],
        "cost_centre": record["cost_centre"],
        "agency": record["agency"],
        "home_market": record["home_market"],
        "manager_id": record["manager_id"],
        "department": request.get("department"),
        "requested_role_templates": list(request.get("requested_role_templates") or []),
        "business_justification": request.get("business_justification") or "",
    }


def build_fleet_it_access_request_employee_lookup_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="employee_lookup",
        name="deterministic_employee_lookup",
        executor_type="deterministic",
        fn=_employee_lookup_execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )
