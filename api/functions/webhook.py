# src/functions/webhook.py
"""
Helper for emitting orchestration events to FastAPI's /internal/durable-event endpoint.

Used by graph executors to track per-step + per-executor activity so the UI can render
the Orchestration tab + right-rail Orchestration feed.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import httpx


WEBHOOK_URL = os.getenv("FASTAPI_WEBHOOK_URL", "http://localhost:3101/internal/durable-event")


def _signed_headers(body: bytes) -> dict[str, str]:
    """Build headers for the durable-event POST. Adds the
    ``X-Durable-Event-Signature`` HMAC-SHA256 header when
    ``DURABLE_EVENT_SECRET`` is configured (the FastAPI route requires it;
    see api/server/routes/internal_durable_event.py)."""
    headers = {"Content-Type": "application/json"}
    secret = os.getenv("DURABLE_EVENT_SECRET")
    if secret:
        headers["X-Durable-Event-Signature"] = hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
    return headers


def _serialise(workflow_id: str, instance_id: str | None, kind: str, payload: dict) -> bytes:
    return json.dumps(
        {"workflow_id": workflow_id, "instance_id": instance_id, "kind": kind, "payload": payload}
    ).encode("utf-8")


async def emit(workflow_id: str, instance_id: str | None, kind: str, payload: dict) -> None:
    """Best-effort webhook emit. Failures are swallowed so workflows don't break on transient
    FastAPI hiccups."""
    body = _serialise(workflow_id, instance_id, kind, payload)
    try:
        async with httpx.AsyncClient() as c:
            await c.post(WEBHOOK_URL, content=body, headers=_signed_headers(body), timeout=5)
    except Exception:
        pass


def emit_sync(workflow_id: str, instance_id: str | None, kind: str, payload: dict) -> None:
    """Synchronous variant — safe to call from activity functions that run inside
    the Functions host's already-running event loop (asyncio.run() raises
    'cannot be called from a running event loop' in that context)."""
    body = _serialise(workflow_id, instance_id, kind, payload)
    try:
        with httpx.Client() as c:
            c.post(WEBHOOK_URL, content=body, headers=_signed_headers(body), timeout=5)
    except Exception:
        pass
