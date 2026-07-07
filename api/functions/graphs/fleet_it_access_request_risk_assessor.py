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
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_it_access_request_risk_assessor
from api.functions.graphs.executors.validators import validate_fleet_it_access_request_risk_assessor_schema


def build_fleet_it_access_request_risk_assessor_workflow() -> Workflow:
    return build_linear_workflow([
        ("risk_assessor", "agent_risk_assessor", "agent", agent_fleet_it_access_request_risk_assessor.execute),
        ("val_risk_assessor", "validate_fleet_it_access_request_risk_assessor_schema", "validator", validate_fleet_it_access_request_risk_assessor_schema.execute),
    ])
