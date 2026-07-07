"""Phase 2 (Access Drafter) graph for Employee onboarding.

  agent_access_drafter -> validate_fleet_employee_onboarding_access_drafter_schema -> terminal

Per brief: agent drafts the day-1 RBAC bundle by listing role templates
that fit the (department, grade), fetching each candidate, and screening
the union for separation-of-duties conflicts. Validator guardrails the
agent payload to the spec shape so Phase 3 can rely on a stable schema.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_employee_onboarding_access_drafter
from api.functions.graphs.executors.validators import validate_fleet_employee_onboarding_access_drafter_schema


def build_fleet_employee_onboarding_access_drafter_workflow() -> Workflow:
    return build_linear_workflow([
        ("access_drafter", "agent_access_drafter", "agent", agent_fleet_employee_onboarding_access_drafter.execute),
        ("val_access_drafter", "validate_fleet_employee_onboarding_access_drafter_schema", "validator", validate_fleet_employee_onboarding_access_drafter_schema.execute),
    ])
