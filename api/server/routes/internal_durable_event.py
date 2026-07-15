from __future__ import annotations
import logging
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ValidationError
from api.server.state import app_state
from api.server.services.webhook_auth import verify_hmac_signature

# inbound: requires X-Durable-Event-Signature; secret in DURABLE_EVENT_SECRET
# (HMAC-SHA256 of the raw request body, hex-encoded; "sha256=" prefix
# tolerated). Verified in :mod:`api.server.services.webhook_auth`. The
# Functions-host emitter (:mod:`api.functions.webhook`) attaches this
# header automatically when the secret is configured.
#
# All ingestion side effects (workflow history, StateStore phase + status
# updates, audit/ledger writes, hub publishing, and workflow-scoped
# FleetEvent emission) live in the non-HTTP
# :class:`~api.server.services.workflow_event_ingestor.WorkflowEventIngestor`
# service (``app_state.workflow_event_ingestor``), which this route delegates
# to after HMAC + body/schema validation. The actor WorldBridge adapter routes
# its own lifecycle events through the same service instance, so both share one
# store/bus/hub/audit and the bounded per-run caches.
router = APIRouter(prefix="/internal")
log = logging.getLogger(__name__)


class DurableEventBody(BaseModel):
    workflow_id: str
    instance_id: str | None = None
    kind: str
    payload: dict


@router.post("/durable-event")
async def receive_durable_event(
    request: Request,
    x_durable_event_signature: str | None = Header(default=None),
):
    raw = await request.body()
    verify_hmac_signature(
        secret_env="DURABLE_EVENT_SECRET",
        signature=x_durable_event_signature,
        body=raw,
    )
    try:
        body = DurableEventBody.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    await app_state.workflow_event_ingestor.ingest(
        body.workflow_id, body.instance_id, body.kind, body.payload
    )
    return {"received": True}
