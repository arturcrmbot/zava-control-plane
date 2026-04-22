# src/functions/graphs/executors/validators/validate_recommendation_authority.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    rec = input.get("resolution_recommendation", {}).get("action")
    return {"ok": rec in {"write-off", "escalate-to-controller", "retry-payment", "request-vendor-clarification"}}
