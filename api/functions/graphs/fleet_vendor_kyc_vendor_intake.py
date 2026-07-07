"""Phase 1 (Vendor Intake) graph for Vendor onboarding & KYC.

  deterministic_vendor_intake -> terminal

Per brief: capture the proposed vendor name + country of incorporation +
proposing agency. Pass forward. No agent, no validator — just a deterministic
function that produces the canonical phase output shape.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow


async def _vendor_intake_execute(input: dict) -> dict:
    """Deterministic vendor intake. Reads `vendor` from the orchestrator
    payload, normalises the three required fields, returns the structured
    record. No I/O, no MCP call — pure normalisation."""
    vendor = input.get("vendor") or {}
    name = vendor.get("name")
    country = vendor.get("country_of_incorporation")
    proposing_agency = vendor.get("proposing_agency")
    if not name or not country or not proposing_agency:
        return {
            "ok": False,
            "blocked_reason": (
                "missing one of vendor.name / vendor.country_of_incorporation "
                "/ vendor.proposing_agency"
            ),
        }
    return {
        "ok": True,
        "vendor_name": name,
        "country_of_incorporation": country,
        "proposing_agency": proposing_agency,
    }


def build_fleet_vendor_kyc_vendor_intake_workflow() -> Workflow:
    return build_linear_workflow([
        ("vendor_intake", "deterministic_vendor_intake", "deterministic", _vendor_intake_execute),
    ])
