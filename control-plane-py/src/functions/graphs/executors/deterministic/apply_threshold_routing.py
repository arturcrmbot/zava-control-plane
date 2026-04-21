# src/functions/graphs/executors/deterministic/apply_threshold_routing.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    # Deterministic demo-hitl injection: force the Approval gate to suspend
    # regardless of amount / policy. Used by the ``demo-hitl`` scenario so
    # an operator can resolve the exception via the UI.
    if input.get("force_hitl"):
        return {"requires_hitl": True, "reason": "demo-hitl injection"}
    amount = input["invoice"]["amount"]
    policy = input["policy"]
    if amount <= policy["auto_threshold"]:
        return {"requires_hitl": False, "decision": "auto-approved"}
    return {"requires_hitl": True, "reason": f"amount {amount} > auto threshold {policy['auto_threshold']}"}
