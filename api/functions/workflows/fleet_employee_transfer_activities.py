"""
Employee transfer between organisations activity functions — registered as
Azure Durable Functions activity triggers (see GRADUATION.md for the
function_app.py diff). Each runs synchronously and wraps an async MAF
Workflow run inside asyncio.run.

Only the three deterministic phases (transfer_intake, employee_lookup,
identity_migration) need per-phase MAF graph activities here. The two
agentic phases (eligibility_check, compensation_remap) ship as
segments-by-default — their activity triggers live in
function_app.py and call `run_segment_b` / `run_segment_d` directly.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_employee_transfer_transfer_intake_workflow,
    build_fleet_employee_transfer_employee_lookup_workflow,
    build_fleet_employee_transfer_identity_migration_workflow,
)


def fleet_employee_transfer_transfer_intake_activity(payload: dict) -> dict:
    """Phase 1 — capture proposed transfer (employee + orgs + effective_date)."""
    return asyncio.run(_run_workflow(
        build_fleet_employee_transfer_transfer_intake_workflow,
        payload,
        "Transfer Intake",
    ))


def fleet_employee_transfer_employee_lookup_activity(payload: dict) -> dict:
    """Phase 2 — read employee grade / cost-centre / agency from Workday."""
    return asyncio.run(_run_workflow(
        build_fleet_employee_transfer_employee_lookup_workflow,
        payload,
        "Employee Lookup",
    ))


def fleet_employee_transfer_identity_migration_activity(payload: dict) -> dict:
    """Phase 7 — provision IdP identity + book handover meetings."""
    return asyncio.run(_run_workflow(
        build_fleet_employee_transfer_identity_migration_workflow,
        payload,
        "Identity Migration",
    ))
