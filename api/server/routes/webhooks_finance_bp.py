"""Inbound Finance-BP Adaptive-Card response webhook for §4.6.

The Adaptive Card composed by `services/adaptive_card.py` posts back here when
the Finance BP clicks Approve / Reject / Needs-info. We translate the click
into a `budget_approval` external event on the Durable orchestration so the
HiringOrchestrator's Phase-1 HITL gate unblocks.

HMAC SHA-256 signature verification is enforced via
:func:`api.server.services.webhook_auth.verify_hmac_signature` against the
shared secret in ``FINANCE_BP_WEBHOOK_SECRET`` (raw request body, hex digest
in the ``X-Finance-BP-Signature`` header).
"""
from __future__ import annotations
from fastapi import APIRouter, Header, HTTPException, Request

from api.server.services.durable_client import raise_orchestration_event
from api.server.services.webhook_auth import verify_hmac_signature
from api.server.state import app_state

router = APIRouter(prefix="/api/webhooks/finance-bp")


@router.post("/{workflow_id}")
async def receive_finance_bp_decision(
    workflow_id: str,
    decision: str,
    request: Request,
    x_finance_bp_signature: str | None = Header(default=None),
):
    raw = await request.body()
    verify_hmac_signature(
        secret_env="FINANCE_BP_WEBHOOK_SECRET",
        signature=x_finance_bp_signature,
        body=raw,
    )
    if decision not in {"approve", "reject", "needs_info"}:
        raise HTTPException(status_code=400, detail="unknown_decision")
    w = app_state.store.get_workflow(workflow_id)
    if not w or not w.orchestration_instance_id:
        raise HTTPException(status_code=404, detail="workflow_or_instance_not_found")
    payload = {"decision": decision, "resolved_by": "finance_bp@zava.com"}
    await raise_orchestration_event(
        w.orchestration_instance_id, "budget_approval", payload,
    )
    return {"ok": True, "workflow_id": workflow_id, "decision": decision}
