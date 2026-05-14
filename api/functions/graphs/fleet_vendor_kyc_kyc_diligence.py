"""Phase 2 (KYC Diligence) graph for Vendor onboarding & KYC.

  agent_kyc_diligence_checker -> validate_kyc_diligence_schema -> terminal

Per brief: agent looks the vendor up in the registry, lists filings (last
24 months), and screens the legal entity against sanctions for both the
vendor's country of incorporation and any country the filings reference.
Validator guardrails the agent payload to the spec shape so Phase 3 can
rely on a stable schema.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_fleet_vendor_kyc_kyc_diligence
from api.functions.graphs.executors.validators import validate_fleet_vendor_kyc_kyc_diligence_schema


def build_fleet_vendor_kyc_kyc_diligence_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="kyc_diligence",
        name="agent_kyc_diligence_checker",
        executor_type="agent",
        fn=agent_fleet_vendor_kyc_kyc_diligence.execute,
    )
    n2 = TrackedExecutor(
        id="val_kyc_diligence",
        name="validate_kyc_diligence_schema",
        executor_type="validator",
        fn=validate_fleet_vendor_kyc_kyc_diligence_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
