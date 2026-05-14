"""Phase 3 (Calibration Drafter) graph for Performance review.

  agent_calibration_drafter -> validate_fleet_perf_review_calibration_drafter_schema -> terminal

Per brief: agent drafts a proposed rating + narrative by combining the
cycle's OKR results with the grade-band distribution norm and the
reviewee's calibration history. Validator guardrails the agent payload
so the HR persona policy can rely on `distribution_fit` taking a
known value.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_fleet_perf_review_calibration_drafter
from api.functions.graphs.executors.validators import validate_fleet_perf_review_calibration_drafter_schema


def build_fleet_perf_review_calibration_drafter_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="calibration_drafter",
        name="agent_calibration_drafter",
        executor_type="agent",
        fn=agent_fleet_perf_review_calibration_drafter.execute,
    )
    n2 = TrackedExecutor(
        id="val_calibration_drafter",
        name="validate_fleet_perf_review_calibration_drafter_schema",
        executor_type="validator",
        fn=validate_fleet_perf_review_calibration_drafter_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
