# src/functions/graphs/executors/deterministic/record_decision.py
from __future__ import annotations
from api.functions.graphs._common import call_mcp, D365_URL


async def execute(input: dict) -> dict:
    workflow_id = input["workflow_id"]
    gl = input["gl_decision"]["gl_account_id"]
    cc = input["cost_centre_decision"]["cost_centre_id"]
    res = await call_mcp(
        D365_URL, "postGLEntry", {"glAccountId": gl, "amount": input["invoice"]["amount"], "workflowId": workflow_id},
        workflow_id=input.get("workflow_id"),
        instance_id=input.get("instance_id"),
    )
    return {"posted": res, "cost_centre_id": cc}
