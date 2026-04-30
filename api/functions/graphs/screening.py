# src/functions/graphs/screening.py
"""POC2 Phase 5 (Screening) graph.

Spine stub. Track A wires this to the `auto-shortlister` skill emitting a
verdict in {"low", "borderline", "strong"} that drives Phase 6 voice gating
in the orchestrator.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_screening_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="hiring_screening",
        name="agent_auto_shortlister",
        executor_type="agent",
        fn=agent_hiring_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_screening",
        name="validate_screening_schema",
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
