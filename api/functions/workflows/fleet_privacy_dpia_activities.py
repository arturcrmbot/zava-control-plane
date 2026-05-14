"""Privacy DPIA activity functions."""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_privacy_dpia_dpia_intake_workflow,
    build_fleet_privacy_dpia_risk_classify_workflow,
    build_fleet_privacy_dpia_authority_resolve_workflow,
)


def fleet_privacy_dpia_dpia_intake_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(
        build_fleet_privacy_dpia_dpia_intake_workflow, payload, "DPIA Intake",
    ))


def fleet_privacy_dpia_risk_classify_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(
        build_fleet_privacy_dpia_risk_classify_workflow, payload, "Risk Classify",
    ))


def fleet_privacy_dpia_authority_resolve_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(
        build_fleet_privacy_dpia_authority_resolve_workflow, payload, "Authority Resolve",
    ))
