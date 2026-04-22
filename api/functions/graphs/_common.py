# src/functions/graphs/_common.py
from __future__ import annotations
import os
import time
import httpx


WORKDAY_URL = os.getenv("WORKDAY_MCP_URL", "http://localhost:4101")
D365_URL = os.getenv("D365_MCP_URL", "http://localhost:4102")
MACONOMY_URL = os.getenv("MACONOMY_MCP_URL", "http://localhost:4103")
PAYMENT_URL = os.getenv("PAYMENT_MCP_URL", "http://localhost:4104")


async def call_mcp(base_url: str, tool: str, args: dict) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{base_url}/mcp/call/{tool}", json=args, timeout=10)
        r.raise_for_status()
        return r.json()


def now_ms() -> int:
    return int(time.time() * 1000)
