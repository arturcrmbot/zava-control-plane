"""
Purchase Order activity functions — registered as Azure Durable Functions
activity triggers.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_fleet_purchase_order_po_lookup_workflow,
    build_fleet_purchase_order_supplier_check_workflow,
    build_fleet_purchase_order_authority_resolve_workflow,
)


def fleet_purchase_order_po_lookup_activity(payload: dict) -> dict:
    """Phase 1 — read the PO record (vendor, amount, category, supplier flag)."""
    return asyncio.run(_run_workflow(
        build_fleet_purchase_order_po_lookup_workflow,
        payload,
        "PO Lookup",
    ))


def fleet_purchase_order_supplier_check_activity(payload: dict) -> dict:
    """Phase 2 — supplier-on-approved-list check + budget headroom."""
    return asyncio.run(_run_workflow(
        build_fleet_purchase_order_supplier_check_workflow,
        payload,
        "Supplier Check",
    ))


def fleet_purchase_order_authority_resolve_activity(payload: dict) -> dict:
    """Phase 3 — call the matrix to resolve the right approver for this value."""
    return asyncio.run(_run_workflow(
        build_fleet_purchase_order_authority_resolve_workflow,
        payload,
        "Authority Resolve",
    ))
