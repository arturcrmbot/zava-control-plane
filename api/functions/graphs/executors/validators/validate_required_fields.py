# src/functions/graphs/executors/validators/validate_required_fields.py
"""Required-fields validator for the expense-claim Phase 1 (Intake) graph.

The Week 1 invoice form (vendor_id / po_ref) was retargeted in the Week 2 pivot;
spec §5.2 calls for one-line retarget to the expense schema. The legacy invoice
intake graph builder is no longer wired into the active orchestrator.
"""
from __future__ import annotations

REQUIRED = {"category", "amount", "currency", "market", "vendor"}


async def execute(input: dict) -> dict:
    fields = input.get("extracted", {}) or {}
    missing = [r for r in REQUIRED if not fields.get(r)]
    return {"ok": len(missing) == 0, "missing": missing, "extracted": fields}
