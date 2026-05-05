"""
AP invoice activity functions — registered as Azure Durable Functions
activity triggers. Each runs synchronously and wraps an async MAF Workflow
run inside asyncio.run.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_ap_invoice_invoice_lookup_workflow,
    build_fleet_ap_invoice_three_way_match_workflow,
)


def fleet_ap_invoice_invoice_lookup_activity(payload: dict) -> dict:
    """Phase 1 — read the invoice record (vendor, amount, GL code, cost centre, due date)."""
    return asyncio.run(_run_workflow(
        build_fleet_ap_invoice_invoice_lookup_workflow,
        payload,
        "Invoice Lookup",
    ))


def fleet_ap_invoice_three_way_match_activity(payload: dict) -> dict:
    """Phase 2 — three-way match the invoice against PO and goods-receipt note."""
    return asyncio.run(_run_workflow(
        build_fleet_ap_invoice_three_way_match_workflow,
        payload,
        "Three-Way Match",
    ))
