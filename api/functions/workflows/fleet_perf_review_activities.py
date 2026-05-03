"""
Performance review activity functions — registered as Azure Durable
Functions activity triggers (see GRADUATION.md for the function_app.py
diff). Each runs synchronously and wraps an async MAF Workflow run inside
asyncio.run.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_perf_review_employee_lookup_workflow,
    build_fleet_perf_review_peer_feedback_aggregator_workflow,
    build_fleet_perf_review_calibration_drafter_workflow,
)


def fleet_perf_review_employee_lookup_activity(payload: dict) -> dict:
    """Phase 1 — read the reviewee's grade, cost-centre, agency and home market from Workday HR."""
    return asyncio.run(_run_workflow(
        build_fleet_perf_review_employee_lookup_workflow,
        payload,
        "Employee Lookup",
    ))


def fleet_perf_review_peer_feedback_aggregator_activity(payload: dict) -> dict:
    """Phase 2 — agent collects 360-degree peer reviews, re-confirms the reporting line, pulls OKR results; validator guards schema."""
    return asyncio.run(_run_workflow(
        build_fleet_perf_review_peer_feedback_aggregator_workflow,
        payload,
        "Peer Feedback Aggregator",
    ))


def fleet_perf_review_calibration_drafter_activity(payload: dict) -> dict:
    """Phase 3 — agent drafts proposed rating + narrative against grade-band distribution and calibration history; validator guards schema."""
    return asyncio.run(_run_workflow(
        build_fleet_perf_review_calibration_drafter_workflow,
        payload,
        "Calibration Drafter",
    ))
