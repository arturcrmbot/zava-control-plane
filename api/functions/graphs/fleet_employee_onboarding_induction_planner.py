"""Phase 4 (Induction Planner) graph for Employee onboarding.

  agent_induction_planner -> validate_fleet_employee_onboarding_induction_planner_schema -> terminal

Per brief: agent finds a 90-minute induction slot within the joiner's
first two weeks across joiner + buddy + line manager, looks up a room in
the joiner's home office, and books the event. Validator guardrails the
agent payload to the spec shape.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_fleet_employee_onboarding_induction_planner
from api.functions.graphs.executors.validators import validate_fleet_employee_onboarding_induction_planner_schema


def build_fleet_employee_onboarding_induction_planner_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="induction_planner",
        name="agent_induction_planner",
        executor_type="agent",
        fn=agent_fleet_employee_onboarding_induction_planner.execute,
    )
    n2 = TrackedExecutor(
        id="val_induction_planner",
        name="validate_fleet_employee_onboarding_induction_planner_schema",
        executor_type="validator",
        fn=validate_fleet_employee_onboarding_induction_planner_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
