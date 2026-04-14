# src/functions/graphs/executors/validators/validate_required_fields.py
from __future__ import annotations

REQUIRED = {"vendor_id", "amount", "po_ref", "currency"}


async def execute(input: dict) -> dict:
    fields = input.get("extracted", {})
    missing = [r for r in REQUIRED if not fields.get(r)]
    return {"ok": len(missing) == 0, "missing": missing, "extracted": fields}
