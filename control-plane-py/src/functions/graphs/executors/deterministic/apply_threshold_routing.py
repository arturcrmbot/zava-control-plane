# src/functions/graphs/executors/deterministic/apply_threshold_routing.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    amount = input["invoice"]["amount"]
    policy = input["policy"]
    if amount <= policy["auto_threshold"]:
        return {"requires_hitl": False, "decision": "auto-approved"}
    return {"requires_hitl": True, "reason": f"amount {amount} > auto threshold {policy['auto_threshold']}"}
