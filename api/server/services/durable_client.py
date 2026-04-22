# src/server/services/durable_client.py
"""
HTTP-based wrapper for the Azure Durable Functions HTTP API.

Calls the `func start` host's HTTP starter at /api/orchestrators/{functionName}
to start orchestrations. The starter response includes a sendEventPostUri
template that we use to raise external events for HITL.

Per-instance state (sendEventPostUri) is cached in memory so we can fire
events later without storing the full URL in the workflow record.
"""
from __future__ import annotations
import os
import re
from typing import Any
import httpx


FUNCTIONS_HOST = os.getenv("FUNCTIONS_HOST", "http://localhost:7071")
ORCHESTRATOR_NAME = "InvoiceP2POrchestrator"

# Cache of instance_id -> sendEventPostUri template
# (templates have {eventName} placeholder)
_send_event_uris: dict[str, str] = {}


async def schedule_new_orchestration(payload: dict, function_name: str = ORCHESTRATOR_NAME) -> dict:
    """Start a new orchestration via the func host's HTTP starter.
    Returns the AF-standard response dict including 'id' (instance_id) and various URIs."""
    url = f"{FUNCTIONS_HOST}/api/orchestrators/{function_name}"
    async with httpx.AsyncClient() as c:
        r = await c.post(url, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        # Cache sendEventPostUri template if present
        if "id" in data and "sendEventPostUri" in data:
            _send_event_uris[data["id"]] = data["sendEventPostUri"]
        return data


async def raise_orchestration_event(instance_id: str, event_name: str, event_data: Any) -> None:
    """Raise an external event on a running orchestration (resumes wait_for_external_event)."""
    template = _send_event_uris.get(instance_id)
    if template:
        # Substitute {eventName} placeholder in the template URI
        uri = template.replace("{eventName}", event_name)
    else:
        # Fallback: use the standard AF Durable URL shape
        uri = f"{FUNCTIONS_HOST}/runtime/webhooks/durabletask/instances/{instance_id}/raiseEvent/{event_name}?taskHub=InvoiceP2PHub&connection=Storage"
    async with httpx.AsyncClient() as c:
        r = await c.post(uri, json=event_data, timeout=10)
        r.raise_for_status()


async def get_orchestration_status(instance_id: str) -> dict | None:
    """Get the current status of an orchestration. Returns None on 404."""
    uri = f"{FUNCTIONS_HOST}/runtime/webhooks/durabletask/instances/{instance_id}?taskHub=InvoiceP2PHub&connection=Storage"
    async with httpx.AsyncClient() as c:
        try:
            r = await c.get(uri, timeout=5)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return None
