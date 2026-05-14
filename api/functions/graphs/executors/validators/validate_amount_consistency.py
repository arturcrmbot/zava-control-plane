# src/functions/graphs/executors/validators/validate_amount_consistency.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    extracted = input["extracted"]
    line_items = extracted.get("line_items", [])
    if not line_items:
        return {"ok": True, "extracted": extracted}
    line_sum = sum(li.get("qty", 1) * li.get("unit_price", 0) for li in line_items)
    diff = abs(line_sum - extracted["amount"])
    tolerance = max(extracted["amount"] * 0.01, 1.0)
    return {"ok": diff <= tolerance, "line_sum": line_sum, "diff": diff, "extracted": extracted}
