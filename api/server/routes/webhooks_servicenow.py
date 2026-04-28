"""Inbound ServiceNow webhook for IT Ops surface (§4.6 multi-surface convergence).

POC2 Phase 10 (Onboarding) opens a ServiceNow JML ticket. When IT Ops resolves
the ticket (or escalates), they post back here. The webhook correlates the
incident id to a Durable orchestration instance and either:
  - resolves any open exception of `category: "itops_blocked"`, or
  - raises an `itops_resolved` external event on the orchestration.

Signed HMAC verification is stubbed for the local demo (the ServiceNow mock
isn't signing) — production wires HMAC SHA-256 against a shared secret read
from Key Vault.
"""
from __future__ import annotations
import time
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from api.server.state import app_state
from api.shared.events import FleetEvent

router = APIRouter(prefix="/api/webhooks/servicenow")


class ServiceNowWebhookBody(BaseModel):
    incident_id: str
    workflow_id: str | None = None
    status: str  # "resolved" | "escalated" | "comment"
    note: str | None = None
    actor: str | None = None


def _verify_signature(_signature: str | None) -> None:
    # Stubbed for the local demo. Production: HMAC SHA-256 over body bytes
    # against `SERVICENOW_WEBHOOK_SECRET` from env.
    return


@router.post("")
async def receive_servicenow_event(
    body: ServiceNowWebhookBody,
    x_servicenow_signature: str | None = Header(default=None),
):
    _verify_signature(x_servicenow_signature)

    if body.status not in {"resolved", "escalated", "comment"}:
        raise HTTPException(status_code=400, detail="unknown_status")

    if body.workflow_id is None:
        return {"ok": True, "ignored": "no_workflow_correlation"}

    wid = body.workflow_id
    now = time.time()

    # Drop any open IT-ops-blocked exceptions on resolve.
    if body.status == "resolved":
        for e in app_state.store.list_exceptions(include_resolved=False):
            if e.workflow_id == wid and e.category == "itops_blocked":
                app_state.store.resolve_exception(e.id, body.actor or "servicenow:itops")
        app_state.bus.emit(FleetEvent(
            type="workflow.itops.resolved", workflow_id=wid, at=now,
        ))

    # Mirror onto orchestration-history so the UI's incident-lane shows it.
    app_state.orchestration_history.setdefault(wid, []).append({
        "kind": "servicenow.event",
        "payload": {
            "incident_id": body.incident_id,
            "status": body.status,
            "note": body.note,
            "actor": body.actor,
        },
        "at": now,
    })
    app_state.hub.broadcast("orchestration", {
        "kind": "servicenow.event",
        "workflow_id": wid,
        "payload": body.model_dump(),
    })
    return {"ok": True, "incident_id": body.incident_id, "workflow_id": wid}
