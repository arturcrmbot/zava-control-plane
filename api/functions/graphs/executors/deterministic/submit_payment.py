# src/functions/graphs/executors/deterministic/submit_payment.py
from __future__ import annotations
from api.functions.graphs._common import call_mcp, PAYMENT_URL


async def execute(input: dict) -> dict:
    """Hook-gated non-revocable action: refuse if no human approval entry on the action ledger."""
    ledger = input.get("action_ledger", [])
    has_human_approval = any(le.get("actor_kind") == "human" and "approve" in le.get("action", "").lower() for le in ledger)
    if input.get("requires_hitl") and not has_human_approval:
        return {"ok": False, "blocked": "requires human approval"}
    file_id = input["payment_file"]["paymentFileId"]
    res = await call_mcp(
        PAYMENT_URL, "submitPayment", {"paymentFileId": file_id, "simulateTimeout": False},
        workflow_id=input.get("workflow_id"),
        instance_id=input.get("instance_id"),
    )
    return {"ok": True, "result": res}
