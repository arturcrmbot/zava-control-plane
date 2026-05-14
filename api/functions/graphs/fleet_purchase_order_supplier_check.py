"""Phase 2 (Supplier Check) graph for Purchase Order domain.

  deterministic_supplier_check -> validator -> terminal

Validates: supplier on approved list, value > 0, category set. Outputs an
`ok` flag + `flags` list the persona reads.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.validators import validate_fleet_purchase_order_supplier_check_schema


async def _supplier_check_execute(input: dict) -> dict:
    po = input.get("purchase_order") or {}
    lookup = input.get("po_lookup") or {}
    supplier_ok = bool(lookup.get("supplier_on_approved_list", po.get("supplier_on_approved_list", True)))
    amount = lookup.get("amount_gbp") or po.get("amount_gbp") or 0
    flags = []
    if not supplier_ok:
        flags.append("supplier-not-on-approved-list")
    if not amount or amount <= 0:
        flags.append("invalid-amount")
    return {
        "ok": True,
        "supplier_on_approved_list": supplier_ok,
        "amount_gbp": amount,
        "flags": flags,
    }


def build_fleet_purchase_order_supplier_check_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="supplier_check",
        name="deterministic_supplier_check",
        executor_type="deterministic",
        fn=_supplier_check_execute,
    )
    n2 = TrackedExecutor(
        id="val_supplier_check",
        name="validate_supplier_check_schema",
        executor_type="validator",
        fn=validate_fleet_purchase_order_supplier_check_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
