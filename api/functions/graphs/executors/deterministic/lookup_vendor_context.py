# src/functions/graphs/executors/deterministic/lookup_vendor_context.py
from __future__ import annotations
from api.functions.graphs._common import call_mcp, WORKDAY_URL


async def execute(input: dict) -> dict:
    vendor_id = input["vendor"]["id"]
    v = await call_mcp(
        WORKDAY_URL, "getVendor", {"vendorId": vendor_id},
        workflow_id=input.get("workflow_id"),
        instance_id=input.get("instance_id"),
    )
    return {"vendor_context": v}
