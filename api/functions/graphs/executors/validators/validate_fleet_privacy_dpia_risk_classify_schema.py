"""Schema validator for Privacy DPIA risk-classify phase output."""
from __future__ import annotations


async def execute(input: dict) -> dict:
    payload = input or {}
    if payload.get("ok") is not True:
        return {"ok": False, "blocked_reason": "risk_classify did not return ok=True", "risk_classify": payload}

    rt = payload.get("risk_tier")
    if rt not in ("low_risk", "high_risk"):
        return {"ok": False, "blocked_reason": f"risk_tier must be low_risk|high_risk; got {rt!r}", "risk_classify": payload}

    geo = payload.get("geography")
    if geo not in ("EMEA", "AMER", "APAC", "*"):
        return {"ok": False, "blocked_reason": f"geography must be EMEA|AMER|APAC; got {geo!r}", "risk_classify": payload}

    flags = payload.get("flags")
    if not isinstance(flags, list):
        return {"ok": False, "blocked_reason": "flags must be a list", "risk_classify": payload}

    return {"ok": True, "risk_classify": payload}
