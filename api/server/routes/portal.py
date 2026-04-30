"""Candidate portal routes — public /apply + token-authed /status, /offer.

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Tasks 5-7, 13.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Form, HTTPException, UploadFile, File

from api.server.services.durable_client import raise_orchestration_event
from api.server.services.magic_link import (
    MagicLinkAlreadyConsumed,
    MagicLinkExpired,
)
from api.server.state import app_state
from api.shared.events import FleetEvent

router = APIRouter(prefix="/api/portal", tags=["portal"])


# ----------------------------------------------------------------- Task 5: apply


@router.post("/apply", status_code=202)
async def apply(
    role_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    cv: UploadFile = File(...),
):
    """Public application intake.

    Validates a PDF CV upload, persists the bytes to blob storage (Azurite
    in dev; real Storage in cloud), creates a candidate record, attaches it
    to the existing HiringOrchestrator workflow keyed by `role_id`, and
    emits a `candidate.applied` event so the Triage phase can pick it up.

    Returns 415 if the upload isn't application/pdf, 404 if no workflow is
    seeded for the role, 503 if blob storage isn't configured.
    """
    if cv.content_type != "application/pdf":
        raise HTTPException(415, "cv must be application/pdf")
    if app_state.blob_store is None:
        raise HTTPException(
            503,
            "blob storage unavailable — set AZURE_STORAGE_CONNECTION_STRING",
        )
    cv_bytes = await cv.read()
    candidate_id = f"C-{uuid.uuid4().hex[:8].upper()}"
    cv_blob_name = f"cvs/{candidate_id}.pdf"
    cv_url = app_state.blob_store.put(
        cv_blob_name, cv_bytes, content_type="application/pdf",
    )
    candidate = {
        "id": candidate_id,
        "name": name,
        "email": email,
        "cv_url": cv_url,
        "role_id": role_id,
    }
    workflow_id = app_state.store.attach_candidate_to_role(role_id, candidate)
    if workflow_id is None:
        raise HTTPException(404, f"no workflow for role_id={role_id}")
    app_state.bus.emit(FleetEvent(
        type="candidate.applied",
        workflow_id=workflow_id,
        candidate_id=candidate_id,
        role_id=role_id,
    ))
    return {
        "status": "submitted",
        "candidate_id": candidate_id,
        "workflow_id": workflow_id,
    }


# ----------------------------------------------------- Task 6: token-authed status


@router.get("/status/{token}")
async def status(token: str):
    """Phase-aware candidate-facing view, gated by a status-scope magic link.

    `peek` not `consume` — a status link is repeatable so the candidate can
    refresh the page across the multi-day hiring lifecycle.
    """
    try:
        payload = app_state.magic_links.peek(token, scope="status")
    except MagicLinkExpired:
        raise HTTPException(410, "link expired")
    except ValueError:
        # Wrong scope — surface as 404 so we don't leak that the token exists.
        raise HTTPException(404, "invalid token")
    if payload is None:
        raise HTTPException(404, "invalid token")
    candidate = app_state.store.get_candidate(payload["candidate_id"])
    if candidate is None:
        raise HTTPException(404, "candidate not found")
    workflow = app_state.store.get_workflow(candidate.get("workflow_id", ""))
    phase = workflow.current_phase if workflow else None
    # Phase-driven hints for the portal UI. Optional fields land on the
    # workflow.metadata dict once the relevant agent emits them; we surface
    # them straight through.
    meta = (workflow.metadata if workflow else {}) or {}
    return {
        "candidate": candidate,
        "phase": phase,
        "next_action": _next_action_for_phase(phase),
        "offer_letter_url": meta.get("offer_letter_url") if phase == "Offer" else None,
        "onboarding_video_url": meta.get("onboarding_video_url") if phase == "Onboarding" else None,
        "voice_transcript": candidate.get("voice_transcript", []),
    }


def _next_action_for_phase(phase) -> str | None:
    """Map a workflow phase to a candidate-side call-to-action label."""
    if phase == "Screening":
        return "rsvp_screening"
    if phase == "Interview":
        return "rsvp_interview"
    if phase == "Offer":
        return "decide_offer"
    return None


# ----------------------------------------------------- Task 7: offer accept/decline


@router.post("/offer/{token}")
async def decide_offer(token: str, decision: str):
    """Single-use accept/decline endpoint for an offer-scope magic link.

    Consumes the token (single_use=True at issuance), raises an
    `offer_decision` external event on the underlying HiringOrchestrator
    instance so the workflow resumes Phase 9, and emits an `offer.decided`
    bus event for the Control Plane.
    """
    if decision not in {"accept", "decline"}:
        raise HTTPException(400, "decision must be accept|decline")
    try:
        payload = app_state.magic_links.consume(token, scope="offer")
    except MagicLinkAlreadyConsumed:
        raise HTTPException(409, "already decided")
    except MagicLinkExpired:
        raise HTTPException(410, "link expired")
    except ValueError:
        raise HTTPException(404, "invalid or expired")
    candidate = app_state.store.get_candidate(payload["candidate_id"])
    if candidate is None:
        raise HTTPException(404, "candidate not found")
    instance_id = candidate.get("instance_id")
    if instance_id:
        try:
            await raise_orchestration_event(
                instance_id, "offer_decision", {"decision": decision},
            )
        except Exception as exc:  # pragma: no cover — surfaces in logs
            # The orchestration may already be terminal; we still want the
            # event to flow so the Control Plane records the decision.
            print(f"[portal] raise_orchestration_event failed: {exc}")
    app_state.bus.emit(FleetEvent(
        type="offer.decided",
        workflow_id=candidate.get("workflow_id"),
        candidate_id=candidate["id"],
        offer_decision=decision,
    ))
    return {"ok": True, "decision": decision}
