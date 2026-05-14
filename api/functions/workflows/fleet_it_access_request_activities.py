"""
IT access request activity functions — registered as Azure Durable
Functions activity triggers (see GRADUATION.md for the function_app.py
diff). Each runs synchronously and wraps an async MAF Workflow run inside
asyncio.run.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_it_access_request_employee_lookup_workflow,
    build_fleet_it_access_request_rbac_resolver_workflow,
    build_fleet_it_access_request_risk_assessor_workflow,
)


def fleet_it_access_request_employee_lookup_activity(payload: dict) -> dict:
    """Phase 1 — read requester grade + cost-centre + agency from Workday HR."""
    return asyncio.run(_run_workflow(
        build_fleet_it_access_request_employee_lookup_workflow,
        payload,
        "Employee Lookup",
    ))


def fleet_it_access_request_rbac_resolver_activity(payload: dict) -> dict:
    """Phase 2 — agent enumerates role templates and screens for SoD; validator guards schema."""
    return asyncio.run(_run_workflow(
        build_fleet_it_access_request_rbac_resolver_workflow,
        payload,
        "RBAC Resolver",
    ))


def fleet_it_access_request_risk_assessor_activity(payload: dict) -> dict:
    """Phase 3 — agent scores per-role and overall risk; validator guards schema."""
    return asyncio.run(_run_workflow(
        build_fleet_it_access_request_risk_assessor_workflow,
        payload,
        "Risk Assessor",
    ))
