# src/functions/graphs/budget.py
"""POC2 Phase 1 (Budget) graph.

Spine stub: agent_hiring_stub -> validate_hiring_stub -> terminal. Track A
replaces the agent with a real budget-checker skill that calls
`workday_position` + emits the Finance BP Adaptive Card payload.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_budget_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="hiring_budget",
        name="agent_budget_checker",
        executor_type="agent",
        fn=agent_hiring_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_budget",
        name="validate_budget_schema",
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
