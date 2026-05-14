"""Phase 1 (PO Lookup) graph for Purchase Order domain.

  deterministic_po_lookup -> terminal

Reads `purchase_order.po_id` from the orchestrator payload and returns the
canonical record. Pure pass-through of the synthetic seed corpus.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor


async def _po_lookup_execute(input: dict) -> dict:
    po = input.get("purchase_order") or {}
    po_id = po.get("po_id")
    if not po_id:
        return {"ok": False, "blocked_reason": "missing purchase_order.po_id"}
    return {
        "ok": True,
        "po_id": po_id,
        "vendor": po.get("vendor_name"),
        "amount_gbp": po.get("amount_gbp"),
        "category": po.get("category", "standard"),
        "supplier_on_approved_list": po.get("supplier_on_approved_list", True),
    }


def build_fleet_purchase_order_po_lookup_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="po_lookup",
        name="deterministic_po_lookup",
        executor_type="deterministic",
        fn=_po_lookup_execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )
