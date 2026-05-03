"""Phase 3 (Risk Assessor) graph for IT access request.

  agent_risk_assessor -> validate_fleet_it_access_request_risk_assessor_schema -> terminal

Per brief: agent scores the request as low / medium / high risk by
querying the employee's last 90-day compliance history, the audit
trail for the requested entitlements, and re-fetching each role
template to compute permission depth. Validator guardrails the agent
payload to the spec shape so the line-manager persona policy can rely
on `overall_risk` being one of the canonical values.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_fleet_it_access_request_risk_assessor
from api.functions.graphs.executors.validators import validate_fleet_it_access_request_risk_assessor_schema


def build_fleet_it_access_request_risk_assessor_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="risk_assessor",
        name="agent_risk_assessor",
        executor_type="agent",
        fn=agent_fleet_it_access_request_risk_assessor.execute,
    )
    n2 = TrackedExecutor(
        id="val_risk_assessor",
        name="validate_fleet_it_access_request_risk_assessor_schema",
        executor_type="validator",
        fn=validate_fleet_it_access_request_risk_assessor_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
