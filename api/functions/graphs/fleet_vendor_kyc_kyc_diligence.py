"""Phase 2 (KYC Diligence) graph for Vendor onboarding & KYC.

  agent_kyc_diligence_checker -> validate_kyc_diligence_schema -> terminal

Per brief: agent looks the vendor up in the registry, lists filings (last
24 months), and screens the legal entity against sanctions for both the
vendor's country of incorporation and any country the filings reference.
Validator guardrails the agent payload to the spec shape so Phase 3 can
rely on a stable schema.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_vendor_kyc_kyc_diligence
from api.functions.graphs.executors.validators import validate_fleet_vendor_kyc_kyc_diligence_schema


def build_fleet_vendor_kyc_kyc_diligence_workflow() -> Workflow:
    return build_linear_workflow([
        ("kyc_diligence", "agent_kyc_diligence_checker", "agent", agent_fleet_vendor_kyc_kyc_diligence.execute),
        ("val_kyc_diligence", "validate_kyc_diligence_schema", "validator", validate_fleet_vendor_kyc_kyc_diligence_schema.execute),
    ])
