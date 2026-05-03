"""Phase 1 (Employee Lookup) graph for Performance review.

  deterministic_employee_lookup -> terminal

Per brief: read the reviewee's grade, cost-centre, agency and home market
from Workday HR. Pass forward. No agent, no validator — just a
deterministic call that produces the canonical phase output shape so
downstream phases (and the personae) can read the reviewee's grade and
home market from a single dict.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.server.mcp_tools.workday_hr_employee import get_employee


async def _employee_lookup_execute(input: dict) -> dict:
    """Deterministic employee lookup. Reads `review.employee_id` from the
    orchestrator payload, calls the workday_hr_employee MCP tool directly
    (no agent session — pure I/O), returns the structured record."""
    review = input.get("review") or {}
    employee_id = review.get("employee_id")
    if not employee_id:
        return {"ok": False, "blocked_reason": "missing review.employee_id"}
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


def build_fleet_perf_review_employee_lookup_workflow() -> Workflow:
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
