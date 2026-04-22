# src/functions/graphs/executors/deterministic/lookup_cost_centre_policy.py
from __future__ import annotations
from api.functions.graphs._common import call_mcp, WORKDAY_URL


async def execute(input: dict) -> dict:
    cc = await call_mcp(
        WORKDAY_URL, "getCostCentre", {"costCentreId": "CC-001"},
        workflow_id=input.get("workflow_id"),
        instance_id=input.get("instance_id"),
    )
    return {"cost_centre_policy": cc}
