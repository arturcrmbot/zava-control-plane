"""Contract Review activity functions."""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_contract_review_contract_intake_workflow,
    build_fleet_contract_review_risk_classify_workflow,
    build_fleet_contract_review_authority_resolve_workflow,
)


def fleet_contract_review_contract_intake_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(
        build_fleet_contract_review_contract_intake_workflow,
        payload, "Contract Intake",
    ))


def fleet_contract_review_risk_classify_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(
        build_fleet_contract_review_risk_classify_workflow,
        payload, "Risk Classify",
    ))


def fleet_contract_review_authority_resolve_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(
        build_fleet_contract_review_authority_resolve_workflow,
        payload, "Authority Resolve",
    ))
