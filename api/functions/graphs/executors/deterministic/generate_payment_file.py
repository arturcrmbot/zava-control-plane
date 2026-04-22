# src/functions/graphs/executors/deterministic/generate_payment_file.py
from __future__ import annotations
from api.functions.graphs._common import call_mcp, PAYMENT_URL


async def execute(input: dict) -> dict:
    workflow_id = input["workflow_id"]
    amount = input["invoice"]["amount"]
    res = await call_mcp(
        PAYMENT_URL, "createPaymentFile", {"workflowId": workflow_id, "amount": amount},
        workflow_id=input.get("workflow_id"),
        instance_id=input.get("instance_id"),
    )
    return {"payment_file": res}
