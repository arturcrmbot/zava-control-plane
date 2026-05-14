"""Phase 2 (Policy Fit Check) graph for Travel pre-approval.

  agent_policy_fit_checker -> validate_policy_fit_check_schema -> terminal

Per brief: agent reasons about whether a proposed trip is in-policy and
which cost band it lands in. Validator guardrails the agent payload to the
spec shape so Phase 3 can rely on a stable schema.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_fleet_travel_preapproval_policy_fit_check
from api.functions.graphs.executors.validators import validate_fleet_travel_preapproval_policy_fit_check


def build_fleet_travel_preapproval_policy_fit_check_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="policy_fit_check",
        name="agent_policy_fit_checker",
        executor_type="agent",
        fn=agent_fleet_travel_preapproval_policy_fit_check.execute,
    )
    n2 = TrackedExecutor(
        id="val_policy_fit_check",
        name="validate_policy_fit_check_schema",
        executor_type="validator",
        fn=validate_fleet_travel_preapproval_policy_fit_check.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
