"""Treasury FX activity functions."""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_treasury_fx_op_lookup_workflow,
    build_fleet_treasury_fx_position_check_workflow,
    build_fleet_treasury_fx_authority_resolve_workflow,
)


def fleet_treasury_fx_op_lookup_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(
        build_fleet_treasury_fx_op_lookup_workflow, payload, "Op Lookup",
    ))


def fleet_treasury_fx_position_check_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(
        build_fleet_treasury_fx_position_check_workflow, payload, "Position Check",
    ))


def fleet_treasury_fx_authority_resolve_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(
        build_fleet_treasury_fx_authority_resolve_workflow, payload, "Authority Resolve",
    ))
