"""
Vendor onboarding & KYC activity functions — registered as Azure Durable
Functions activity triggers (see GRADUATION.md for the function_app.py
diff). Each runs synchronously and wraps an async MAF Workflow run inside
asyncio.run.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_vendor_kyc_vendor_intake_workflow,
    build_fleet_vendor_kyc_kyc_diligence_workflow,
    build_fleet_vendor_kyc_ubo_resolver_workflow,
)


def fleet_vendor_kyc_vendor_intake_activity(payload: dict) -> dict:
    """Phase 1 — capture proposed vendor name + country + proposing agency."""
    return asyncio.run(_run_workflow(
        build_fleet_vendor_kyc_vendor_intake_workflow,
        payload,
        "Vendor Intake",
    ))


def fleet_vendor_kyc_kyc_diligence_activity(payload: dict) -> dict:
    """Phase 2 — agent runs registry + filings lookup + entity sanctions screen."""
    return asyncio.run(_run_workflow(
        build_fleet_vendor_kyc_kyc_diligence_workflow,
        payload,
        "KYC Diligence",
    ))


def fleet_vendor_kyc_ubo_resolver_activity(payload: dict) -> dict:
    """Phase 3 — agent enumerates UBOs, screens each, runs adverse-media sweep."""
    return asyncio.run(_run_workflow(
        build_fleet_vendor_kyc_ubo_resolver_workflow,
        payload,
        "UBO Resolver",
    ))
