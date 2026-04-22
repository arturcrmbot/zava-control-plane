# src/functions/graphs/_common.py
from __future__ import annotations
import os
import time
import httpx


WORKDAY_URL = os.getenv("WORKDAY_MCP_URL", "http://localhost:4101")
D365_URL = os.getenv("D365_MCP_URL", "http://localhost:4102")
MACONOMY_URL = os.getenv("MACONOMY_MCP_URL", "http://localhost:4103")
PAYMENT_URL = os.getenv("PAYMENT_MCP_URL", "http://localhost:4104")


async def call_mcp(
    base_url: str,
    tool: str,
    args: dict,
    workflow_id: str | None = None,
    instance_id: str | None = None,
) -> dict:
    """POST to an MCP endpoint. Emits a durable `mcp.call` event with the
    request, response, status, and duration when `workflow_id` is provided
    so the UI's Execution Timeline can render per-call step cards."""
    url = f"{base_url}/mcp/call/{tool}"
    t0 = time.time()
    resp_json: dict
    status_code: int
    async with httpx.AsyncClient() as c:
        try:
            r = await c.post(url, json=args, timeout=10)
            status_code = r.status_code
            resp_json = r.json() if r.is_success else {"error": r.text}
        except Exception as ex:
            resp_json = {"error": str(ex)}
            status_code = 599
    duration_ms = int((time.time() - t0) * 1000)

    if workflow_id is not None:
        # Local import avoids circular deps during module load.
        from api.functions.webhook import emit
        await emit(workflow_id, instance_id, "mcp.call", {
            "tool": tool, "url": url, "method": "POST",
            "request": args, "response": resp_json,
            "status_code": status_code, "duration_ms": duration_ms,
        })

    if status_code >= 400:
        raise RuntimeError(f"mcp {tool} failed: {status_code}")
    return resp_json


def now_ms() -> int:
    return int(time.time() * 1000)
