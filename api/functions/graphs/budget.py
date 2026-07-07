# src/functions/graphs/budget.py
"""POC2 Phase 1 (Budget) graph.

Spine stub: agent_hiring_stub -> validate_hiring_stub -> terminal. Track A
replaces the agent with a real budget-checker skill that calls
`workday_position` + emits the Finance BP Adaptive Card payload.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_budget_workflow() -> Workflow:
    return build_linear_workflow([
        ("hiring_budget", "agent_budget_checker", "agent", agent_hiring_stub.execute),
        ("val_budget", "validate_budget_schema", "validator", validate_hiring_stub.execute),
    ])
