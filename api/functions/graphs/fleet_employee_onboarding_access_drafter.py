"""Phase 2 (Access Drafter) graph for Employee onboarding.

  agent_access_drafter -> validate_fleet_employee_onboarding_access_drafter_schema -> terminal

Per brief: agent drafts the day-1 RBAC bundle by listing role templates
that fit the (department, grade), fetching each candidate, and screening
the union for separation-of-duties conflicts. Validator guardrails the
agent payload to the spec shape so Phase 3 can rely on a stable schema.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_fleet_employee_onboarding_access_drafter
from api.functions.graphs.executors.validators import validate_fleet_employee_onboarding_access_drafter_schema


def build_fleet_employee_onboarding_access_drafter_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="access_drafter",
        name="agent_access_drafter",
        executor_type="agent",
        fn=agent_fleet_employee_onboarding_access_drafter.execute,
    )
    n2 = TrackedExecutor(
        id="val_access_drafter",
        name="validate_fleet_employee_onboarding_access_drafter_schema",
        executor_type="validator",
        fn=validate_fleet_employee_onboarding_access_drafter_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
