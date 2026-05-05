"""Phase 1 (DPIA Intake) graph for Privacy DPIA domain."""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor


async def _dpia_intake_execute(input: dict) -> dict:
    d = input.get("dpia") or {}
    dpia_id = d.get("dpia_id")
    if not dpia_id:
        return {"ok": False, "blocked_reason": "missing dpia.dpia_id"}
    return {
        "ok": True,
        "dpia_id": dpia_id,
        "system_name": d.get("system_name", "Unnamed System"),
        "risk_tier": d.get("risk_tier", "low_risk"),
        "geography": d.get("geography", "EMEA"),
    }


def build_fleet_privacy_dpia_dpia_intake_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="dpia_intake",
        name="deterministic_dpia_intake",
        executor_type="deterministic",
        fn=_dpia_intake_execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )
