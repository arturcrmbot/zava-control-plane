# src/functions/graphs/executors/deterministic/three_way_match.py
from __future__ import annotations
from api.functions.graphs._common import call_mcp, D365_URL


async def execute(input: dict) -> dict:
    invoice = input["invoice"]
    res = await call_mcp(
        D365_URL, "matchPO", {"invoiceAmount": invoice["amount"], "poId": invoice["po_ref"]},
        workflow_id=input.get("workflow_id"),
        instance_id=input.get("instance_id"),
    )
    return {"match": res}
