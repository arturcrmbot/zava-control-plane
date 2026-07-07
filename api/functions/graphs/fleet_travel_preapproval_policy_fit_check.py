"""Phase 2 (Policy Fit Check) graph for Travel pre-approval.

  agent_policy_fit_checker -> validate_policy_fit_check_schema -> terminal

Per brief: agent reasons about whether a proposed trip is in-policy and
which cost band it lands in. Validator guardrails the agent payload to the
spec shape so Phase 3 can rely on a stable schema.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_travel_preapproval_policy_fit_check
from api.functions.graphs.executors.validators import validate_fleet_travel_preapproval_policy_fit_check


def build_fleet_travel_preapproval_policy_fit_check_workflow() -> Workflow:
    return build_linear_workflow([
        ("policy_fit_check", "agent_policy_fit_checker", "agent", agent_fleet_travel_preapproval_policy_fit_check.execute),
        ("val_policy_fit_check", "validate_policy_fit_check_schema", "validator", validate_fleet_travel_preapproval_policy_fit_check.execute),
    ])
