# src/functions/graphs/executors/validators/validate_threshold_authority.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    amount = input["invoice"]["amount"]
    return {"ok": True, "requires_cfo": amount > 50000}
