"""
Travel pre-approval activity functions — registered as Azure Durable
Functions activity triggers (see GRADUATION.md for the function_app.py
diff). Each runs synchronously and wraps an async MAF Workflow run inside
asyncio.run.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_travel_preapproval_employee_lookup_workflow,
    build_fleet_travel_preapproval_policy_fit_check_workflow,
)


def fleet_travel_preapproval_employee_lookup_activity(payload: dict) -> dict:
    """Phase 1 — read employee grade + cost-centre from Workday HR."""
    return asyncio.run(_run_workflow(
        build_fleet_travel_preapproval_employee_lookup_workflow,
        payload,
        "Employee Lookup",
    ))


def fleet_travel_preapproval_policy_fit_check_activity(payload: dict) -> dict:
    """Phase 2 — agent reasons about policy fit + cost band; validator guards schema."""
    return asyncio.run(_run_workflow(
        build_fleet_travel_preapproval_policy_fit_check_workflow,
        payload,
        "Policy Fit Check",
    ))
