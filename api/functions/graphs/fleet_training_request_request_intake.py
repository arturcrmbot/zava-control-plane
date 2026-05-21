"""Phase 1 (Request Intake) graph for Training request.

  deterministic_request_intake -> terminal

Per brief: capture the training request fields (employee_id, topic,
requested_course title, estimated_cost_gbp, target_start_date). Pass
forward. No agent, no validator — just a deterministic pass-through
that produces the canonical phase output shape.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor


async def _request_intake_execute(input: dict) -> dict:
    """Deterministic training request intake. Reads the request fields
    from the orchestrator payload and stamps a canonical output shape."""
    req = input.get("request") or input.get("training_request") or input.get("payload") or {}
    employee_id = req.get("employee_id") or input.get("employee_id")
    topic = req.get("topic") or input.get("topic")
    requested_course = (
        req.get("requested_course") or input.get("requested_course")
    )
    estimated_cost_gbp = (
        req.get("estimated_cost_gbp") or input.get("estimated_cost_gbp")
    )
    target_start_date = (
        req.get("target_start_date") or input.get("target_start_date")
    )

    if not employee_id or not requested_course:
        return {
            "ok": False,
            "blocked_reason": "missing employee_id or requested_course",
        }
    return {
        "ok": True,
        "employee_id": employee_id,
        "topic": topic or "general",
        "requested_course": requested_course,
        "estimated_cost_gbp": estimated_cost_gbp,
        "target_start_date": target_start_date,
    }


def build_fleet_training_request_request_intake_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="request_intake",
        name="deterministic_request_intake",
        executor_type="deterministic",
        fn=_request_intake_execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )
