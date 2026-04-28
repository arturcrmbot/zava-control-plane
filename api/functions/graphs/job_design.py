# src/functions/graphs/job_design.py
"""POC2 Phase 2 (Job Design) graph.

Spine stub. Track A replaces the agent with the `jd-drafter` skill, which
calls `policy_search` for jurisdiction-appropriate JD boilerplate.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_job_design_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="hiring_job_design",
        name="agent_jd_drafter",
        executor_type="agent",
        fn=agent_hiring_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_jd",
        name="validate_jd_schema",
        executor_type="validator",
        fn=validate_hiring_stub.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
