"""
Employee onboarding activity functions — registered as Azure Durable
Functions activity triggers (see GRADUATION.md for the function_app.py
diff). Each runs synchronously and wraps an async MAF Workflow run inside
asyncio.run.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_employee_onboarding_employee_lookup_workflow,
    build_fleet_employee_onboarding_access_drafter_workflow,
    build_fleet_employee_onboarding_induction_planner_workflow,
)


def fleet_employee_onboarding_employee_lookup_activity(payload: dict) -> dict:
    """Phase 1 — read joiner grade + cost-centre + agency from Workday HR."""
    return asyncio.run(_run_workflow(
        build_fleet_employee_onboarding_employee_lookup_workflow,
        payload,
        "Employee Lookup",
    ))


def fleet_employee_onboarding_access_drafter_activity(payload: dict) -> dict:
    """Phase 2 — agent drafts the day-1 RBAC bundle; validator guards schema."""
    return asyncio.run(_run_workflow(
        build_fleet_employee_onboarding_access_drafter_workflow,
        payload,
        "Access Drafter",
    ))


def fleet_employee_onboarding_induction_planner_activity(payload: dict) -> dict:
    """Phase 4 — agent finds a 90-minute slot, picks a room, books the event."""
    return asyncio.run(_run_workflow(
        build_fleet_employee_onboarding_induction_planner_workflow,
        payload,
        "Induction Planner",
    ))
