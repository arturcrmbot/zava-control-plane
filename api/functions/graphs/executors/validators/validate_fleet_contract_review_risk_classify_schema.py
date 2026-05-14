"""Schema validator for Contract Review risk-classify phase output."""
from __future__ import annotations


async def execute(input: dict) -> dict:
    payload = input or {}
    if payload.get("ok") is not True:
        return {"ok": False, "blocked_reason": "risk_classify phase did not return ok=True", "risk_classify": payload}

    ct = payload.get("contract_type")
    if ct not in ("nda", "msa", "sow"):
        return {"ok": False, "blocked_reason": f"contract_type must be nda|msa|sow; got {ct!r}", "risk_classify": payload}

    if not isinstance(payload.get("deviates_from_template"), bool):
        return {"ok": False, "blocked_reason": "deviates_from_template must be bool", "risk_classify": payload}

    amt = payload.get("amount_gbp")
    if not isinstance(amt, (int, float)) or amt < 0:
        return {"ok": False, "blocked_reason": "amount_gbp must be non-negative", "risk_classify": payload}

    flags = payload.get("flags")
    if not isinstance(flags, list):
        return {"ok": False, "blocked_reason": "flags must be a list", "risk_classify": payload}

    return {"ok": True, "risk_classify": payload}
