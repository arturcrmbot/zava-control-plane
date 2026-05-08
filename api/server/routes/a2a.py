"""A2A boundary route for §4.19 (external Personal Agent ↔ internal hiring agent).

A candidate's external Personal Agent can negotiate availability, share extra
context, etc., with our internal hiring-agent. APIM polices the boundary in
the cloud-target architecture (mTLS + signed JWT identity + per-call rate
limits); the local demo simulates this via a single signed POST that lands
here.

The A2A message is recorded in the workflow's ledger and an event is emitted
on the bus so the Control Plane shows the cross-boundary message in the
Execution Timeline.
"""
from __future__ import annotations
import time
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from api.server.state import app_state
from api.shared.events import FleetEvent
from api.shared.types import ActionLedgerEntry

router = APIRouter(prefix="/api/a2a")


class A2AMessage(BaseModel):
    workflow_id: str
    from_pa: str  # PA identity URI, e.g. "did:wpp:candidate:C-101"
    correlation_id: str | None = None
    intent: str  # "availability_propose" | "salary_negotiate" | "request_info"
    body: dict


def _verify_a2a_signature(_signature: str | None) -> None:
    # Stubbed. Production: APIM validates the signed JWT identity + mTLS chain.
    return


@router.post("/inbound")
async def receive_a2a_message(
    msg: A2AMessage,
    x_a2a_signature: str | None = Header(default=None),
):
    _verify_a2a_signature(x_a2a_signature)

    if msg.intent not in {"availability_propose", "salary_negotiate", "request_info"}:
        raise HTTPException(status_code=400, detail="unknown_intent")

    w = app_state.store.get_workflow(msg.workflow_id)
    if w is None:
        raise HTTPException(status_code=404, detail="workflow_not_found")

    now = time.time()
    app_state.store.append_ledger(msg.workflow_id, ActionLedgerEntry(
        workflow_id=msg.workflow_id,
        timestamp=now,
        actor_kind="external",  # type: ignore[arg-type]
        actor_id=msg.from_pa,
        action=f"a2a.{msg.intent}",
        revocable=False,
        details={"correlation_id": msg.correlation_id, "body": msg.body},
    ))

    app_state.bus.emit(FleetEvent(
        type="workflow.a2a.inbound",
        workflow_id=msg.workflow_id,
        from_pa=msg.from_pa,
        intent=msg.intent,
    ))

    # Track E2 wires this through to the live hiring-agent session for an
    # actual reply. For the spine we acknowledge synchronously.
    return {
        "ok": True,
        "workflow_id": msg.workflow_id,
        "correlation_id": msg.correlation_id,
        "ack": True,
        "reply": (
            f"Ack from hiring-agent@zava — your {msg.intent} message is in the "
            f"workflow ledger and the panel will respond inside SLA."
        ),
    }
