"""Schema validator for Purchase Order supplier-check phase output."""
from __future__ import annotations


async def execute(input: dict) -> dict:
    payload = input or {}
    if payload.get("ok") is not True:
        return {"ok": False, "blocked_reason": "supplier_check phase did not return ok=True", "supplier_check": payload}

    if not isinstance(payload.get("supplier_on_approved_list"), bool):
        return {"ok": False, "blocked_reason": "supplier_on_approved_list must be bool", "supplier_check": payload}

    flags = payload.get("flags")
    if not isinstance(flags, list):
        return {"ok": False, "blocked_reason": "flags must be a list", "supplier_check": payload}

    amt = payload.get("amount_gbp")
    if not isinstance(amt, (int, float)) or amt < 0:
        return {"ok": False, "blocked_reason": "amount_gbp must be non-negative", "supplier_check": payload}

    return {"ok": True, "supplier_check": payload}
