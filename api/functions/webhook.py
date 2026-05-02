# src/functions/webhook.py
"""
Helper for emitting orchestration events to FastAPI's /internal/durable-event endpoint.

Used by graph executors to track per-step + per-executor activity so the UI can render
the Orchestration tab + right-rail Orchestration feed.
"""
from __future__ import annotations
import os
import httpx


WEBHOOK_URL = os.getenv("FASTAPI_WEBHOOK_URL", "http://localhost:3001/internal/durable-event")


async def emit(workflow_id: str, instance_id: str | None, kind: str, payload: dict) -> None:
    """Best-effort webhook emit. Failures are swallowed so workflows don't break on transient
    FastAPI hiccups."""
    body = {"workflow_id": workflow_id, "instance_id": instance_id, "kind": kind, "payload": payload}
    try:
        async with httpx.AsyncClient() as c:
            await c.post(WEBHOOK_URL, json=body, timeout=5)
    except Exception:
        pass


def emit_sync(workflow_id: str, instance_id: str | None, kind: str, payload: dict) -> None:
    """Synchronous variant — safe to call from activity functions that run inside
    the Functions host's already-running event loop (asyncio.run() raises
    'cannot be called from a running event loop' in that context)."""
    body = {"workflow_id": workflow_id, "instance_id": instance_id, "kind": kind, "payload": payload}
    try:
        with httpx.Client() as c:
            c.post(WEBHOOK_URL, json=body, timeout=5)
    except Exception:
        pass
