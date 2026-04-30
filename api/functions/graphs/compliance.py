# src/functions/graphs/compliance.py
"""POC2 Phase 8 (Compliance) graph.

Spine stub. Track D wires this to the `jurisdiction-router` skill which
fans out to `betrvg-checker` (DE only) per spec §4.10. USA path is a
no-op compliance summary; DE path adds works-council notification.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_compliance_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="hiring_compliance",
        name="agent_jurisdiction_router",
        executor_type="agent",
        fn=agent_hiring_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_compliance",
        name="validate_compliance_schema",
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
