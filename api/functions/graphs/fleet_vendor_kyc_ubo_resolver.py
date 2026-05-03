"""Phase 3 (UBO Resolver) graph for Vendor onboarding & KYC.

  agent_ubo_resolver -> validate_ubo_resolver_schema -> terminal

Per brief: agent enumerates ultimate beneficial owners (UBOs) of the vendor,
screens each UBO against sanctions, and runs an adverse-media sweep on the
top three UBOs by ownership percentage. Validator guardrails the payload
shape for the finance sign-off persona's decision policy.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_fleet_vendor_kyc_ubo_resolver
from api.functions.graphs.executors.validators import validate_fleet_vendor_kyc_ubo_resolver_schema


def build_fleet_vendor_kyc_ubo_resolver_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="ubo_resolver",
        name="agent_ubo_resolver",
        executor_type="agent",
        fn=agent_fleet_vendor_kyc_ubo_resolver.execute,
    )
    n2 = TrackedExecutor(
        id="val_ubo_resolver",
        name="validate_ubo_resolver_schema",
        executor_type="validator",
        fn=validate_fleet_vendor_kyc_ubo_resolver_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
