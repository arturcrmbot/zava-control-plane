"""Phase 2 (RBAC Resolver) graph for IT access request.

  agent_rbac_resolver -> validate_fleet_it_access_request_rbac_resolver_schema -> terminal

Per brief: agent enumerates the role templates referenced in the request,
fetches each template's permissions, and runs a separation-of-duties check
on the union against the employee's grade-band default entitlements.
Validator guardrails the agent payload to the spec shape so downstream
phases can rely on a stable schema.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_it_access_request_rbac_resolver
from api.functions.graphs.executors.validators import validate_fleet_it_access_request_rbac_resolver_schema


def build_fleet_it_access_request_rbac_resolver_workflow() -> Workflow:
    return build_linear_workflow([
        ("rbac_resolver", "agent_rbac_resolver", "agent", agent_fleet_it_access_request_rbac_resolver.execute),
        ("val_rbac_resolver", "validate_fleet_it_access_request_rbac_resolver_schema", "validator", validate_fleet_it_access_request_rbac_resolver_schema.execute),
    ])
