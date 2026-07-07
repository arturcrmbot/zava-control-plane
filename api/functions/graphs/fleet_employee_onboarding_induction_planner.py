"""Phase 4 (Induction Planner) graph for Employee onboarding.

  agent_induction_planner -> validate_fleet_employee_onboarding_induction_planner_schema -> terminal

Per brief: agent finds a 90-minute induction slot within the joiner's
first two weeks across joiner + buddy + line manager, looks up a room in
the joiner's home office, and books the event. Validator guardrails the
agent payload to the spec shape.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_employee_onboarding_induction_planner
from api.functions.graphs.executors.validators import validate_fleet_employee_onboarding_induction_planner_schema


def build_fleet_employee_onboarding_induction_planner_workflow() -> Workflow:
    return build_linear_workflow([
        ("induction_planner", "agent_induction_planner", "agent", agent_fleet_employee_onboarding_induction_planner.execute),
        ("val_induction_planner", "validate_fleet_employee_onboarding_induction_planner_schema", "validator", validate_fleet_employee_onboarding_induction_planner_schema.execute),
    ])
