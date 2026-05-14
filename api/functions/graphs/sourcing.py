# src/functions/graphs/sourcing.py
"""POC2 Phase 3 (Sourcing) graph.

Spine stub. Track A wires this to the `sourcing-orchestrator` skill that
fans out to `linkedin_search` + `greenhouse_post`.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_sourcing_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="hiring_sourcing",
        name="agent_sourcing_orchestrator",
        executor_type="agent",
        fn=agent_hiring_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_sourcing",
        name="validate_sourcing_schema",
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
