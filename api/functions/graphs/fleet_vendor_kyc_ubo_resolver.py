"""Phase 3 (UBO Resolver) graph for Vendor onboarding & KYC.

  agent_ubo_resolver -> validate_ubo_resolver_schema -> terminal

Per brief: agent enumerates ultimate beneficial owners (UBOs) of the vendor,
screens each UBO against sanctions, and runs an adverse-media sweep on the
top three UBOs by ownership percentage. Validator guardrails the payload
shape for the finance sign-off persona's decision policy.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_vendor_kyc_ubo_resolver
from api.functions.graphs.executors.validators import validate_fleet_vendor_kyc_ubo_resolver_schema


def build_fleet_vendor_kyc_ubo_resolver_workflow() -> Workflow:
    return build_linear_workflow([
        ("ubo_resolver", "agent_ubo_resolver", "agent", agent_fleet_vendor_kyc_ubo_resolver.execute),
        ("val_ubo_resolver", "validate_ubo_resolver_schema", "validator", validate_fleet_vendor_kyc_ubo_resolver_schema.execute),
    ])
