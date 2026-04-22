# src/functions/graphs/executors/deterministic/bank_statement_match.py
from __future__ import annotations
from api.functions.graphs._common import call_mcp, PAYMENT_URL


async def execute(input: dict) -> dict:
    res = await call_mcp(
        PAYMENT_URL, "reconcileStatement", {"statementId": "STMT-2026-04-10"},
        workflow_id=input.get("workflow_id"),
        instance_id=input.get("instance_id"),
    )
    return {"reconciliation": res, "unmatched_items": []}  # demo: zero unmatched (recon agents skip)
