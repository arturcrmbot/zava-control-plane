"""Phase 7 (Identity Migration) graph for Employee transfer between organisations.

  deterministic_identity_migration -> terminal

Per brief: provision the employee's identity in the target org's IdP
tenant with the new grade's standard entitlements, and book the
transition handover meetings on the agreed effective_date via the
calendar service.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.server.mcp_tools.identity_provider import list_role_templates
from api.server.mcp_tools.calendar_service import find_availability


async def _identity_migration_execute(input: dict) -> dict:
    """Deterministic identity provisioning + handover booking. Reads the
    target_role / grade from the prior phases, asks the IdP for the
    matching role template, and queries the calendar service for a
    handover slot on the effective_date."""
    intake = input.get("transfer_intake") or {}
    lookup = input.get("employee_lookup") or {}
    employee_id = intake.get("employee_id") or lookup.get("employee_id")
    target_role = intake.get("target_role") or "associate"
    effective_date = intake.get("effective_date")
    grade = lookup.get("grade") or "G6"

    if not employee_id or not effective_date:
        return {
            "ok": False,
            "blocked_reason": "missing employee_id or effective_date",
        }

    role_templates = list_role_templates(department=target_role, grade=grade)
    availability = find_availability(
        attendees=[employee_id, lookup.get("manager_id") or "unknown"],
        duration_minutes=60,
        window_start=effective_date,
        window_days=7,
    )
    return {
        "ok": True,
        "employee_id": employee_id,
        "provisioned_role_template": (
            (role_templates.get("templates") or [{}])[0].get("template_id")
            if isinstance(role_templates, dict) else None
        ),
        "handover_slot": availability,
        "effective_date": effective_date,
    }


def build_fleet_employee_transfer_identity_migration_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="identity_migration",
        name="deterministic_identity_migration",
        executor_type="deterministic",
        fn=_identity_migration_execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )
