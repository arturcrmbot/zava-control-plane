# src/functions/graphs/interview.py
"""POC2 Phase 7 (Interview) graph.

Spine stub. Track A wires this to the `interview-coordinator` skill calling
`graph_calendar` + `graph_mail` for panel scheduling; HITL waits on panel
RSVPs (handled separately from the orchestrator-level HITL gates).
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_interview_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="hiring_interview",
        name="agent_interview_coordinator",
        executor_type="agent",
        fn=agent_hiring_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_interview",
        name="validate_interview_schema",
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
