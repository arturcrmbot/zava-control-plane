"""Schema validator for Treasury FX position-check phase output."""
from __future__ import annotations


async def execute(input: dict) -> dict:
    payload = input or {}
    if payload.get("ok") is not True:
        return {"ok": False, "blocked_reason": "position_check did not return ok=True", "position_check": payload}

    if not isinstance(payload.get("within_limit"), bool):
        return {"ok": False, "blocked_reason": "within_limit must be bool", "position_check": payload}

    notional = payload.get("notional_gbp")
    limit = payload.get("pair_limit_gbp")
    if not isinstance(notional, (int, float)) or notional < 0:
        return {"ok": False, "blocked_reason": "notional_gbp must be non-negative", "position_check": payload}
    if not isinstance(limit, (int, float)) or limit <= 0:
        return {"ok": False, "blocked_reason": "pair_limit_gbp must be > 0", "position_check": payload}
    if payload["within_limit"] != (notional <= limit):
        return {
            "ok": False,
            "blocked_reason": f"within_limit={payload['within_limit']} disagrees with notional={notional}/limit={limit}",
            "position_check": payload,
        }

    flags = payload.get("flags")
    if not isinstance(flags, list):
        return {"ok": False, "blocked_reason": "flags must be a list", "position_check": payload}

    return {"ok": True, "position_check": payload}
