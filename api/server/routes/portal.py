"""Candidate portal routes — public /apply + token-authed /status, /offer.

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Tasks 5-7, 13.
"""
from __future__ import annotations

import uuid
from pathlib import Path

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
    # Also stage a copy under data/synthetic/hiring/cv-pdfs so the
    # ocr_extract MCP tool (which resolves C-* ids to local paths) can read
    # uploaded CVs the same way it reads the seeded synthetic ones. Without
    # this, cv-crystalliser would fail on real uploads because the tool can't
    # see Azurite blobs.
    _local_pdfs_dir = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "hiring" / "cv-pdfs"
    _local_pdfs_dir.mkdir(parents=True, exist_ok=True)
    (_local_pdfs_dir / f"{candidate_id}.pdf").write_bytes(cv_bytes)
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
    # Look up the candidate's active screen + offer scope tokens (if any)
    # so the portal UI can mint the right call-to-action URL without an
    # extra round-trip. Tokens are filtered to active (unconsumed,
    # unexpired) — list_active() already enforces both conditions.
    active = app_state.magic_links.list_active()
    screen_token = next((r["token"] for r in active
                         if r["candidate_id"] == candidate["id"] and r["scope"] == "screen"), None)
    offer_token = next((r["token"] for r in active
                        if r["candidate_id"] == candidate["id"] and r["scope"] == "offer"), None)
    return {
        "candidate": candidate,
        "phase": phase,
        "next_action": _next_action_for_phase(phase),
        "offer_letter_url": meta.get("offer_letter_url") if phase == "Offer" else None,
        "onboarding_video_url": meta.get("onboarding_video_url") if phase == "Onboarding" else None,
        "voice_transcript": candidate.get("voice_transcript", []),
        "screen_token": screen_token,
        "offer_token": offer_token,
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
    `offer_approval` external event on the underlying HiringOrchestrator
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
            # Event name MUST match the orchestrator's wait_for_external_event
            # in api/functions/workflows/hiring.py — Phase 9 awaits
            # `offer_approval`, not `offer_decision`.
            await raise_orchestration_event(
                instance_id, "offer_approval",
                {"decision": decision, "resolved_by": "candidate_portal"},
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


# --------------------------------------------------- Task 13: admin /links


@router.get("/admin/links")
async def admin_links():
    """Control-Plane fallback for delivering magic links when ACS Email is
    unavailable. Joins the candidate name + email onto each active token row
    so the admin can click-to-copy without a second lookup."""
    rows = app_state.magic_links.list_active()
    out = []
    for row in rows:
        cand = app_state.store.get_candidate(row["candidate_id"]) or {}
        out.append({
            **row,
            "name": cand.get("name"),
            "email": cand.get("email"),
            "role_id": cand.get("role_id"),
            "workflow_id": cand.get("workflow_id"),
        })
    return {"links": out}


# ---------------------------------------------- Recruiter candidate detail
# Surfaced inside the candidate-portal app at /recruiter/c/:id — the
# recruiter-facing view of a single candidate. Joins candidate record +
# workflow + agent reasoning outputs + voice transcript so the recruiter
# (or an evaluator stepping through the demo) can see WHO this is, WHAT
# we learned, and WHAT THE AI DECIDED — not just span names.


@router.get("/admin/candidates")
async def admin_candidates():
    """List every candidate the system knows about, with their workflow phase,
    role, and any active magic links. Powers the recruiter list view at
    /recruiter."""
    candidates = app_state.store.list_candidates()
    active_tokens = app_state.magic_links.list_active()
    by_cid: dict[str, list[dict]] = {}
    for t in active_tokens:
        by_cid.setdefault(t["candidate_id"], []).append(t)

    out = []
    for c in candidates:
        wf = app_state.store.get_workflow(c.get("workflow_id", ""))
        meta = (wf.metadata if wf else {}) or {}
        out.append({
            "candidate_id": c["id"],
            "name": c.get("name"),
            "email": c.get("email"),
            "role_id": c.get("role_id"),
            "role_title": meta.get("role_title"),
            "role_jurisdiction": meta.get("role_jurisdiction"),
            "workflow_id": c.get("workflow_id"),
            "phase": wf.current_phase if wf else None,
            "status": wf.status if wf else None,
            "awaiting_reason": meta.get("awaiting_reason"),
            "active_tokens": [t["scope"] for t in by_cid.get(c["id"], [])],
        })
    return {"candidates": out}


@router.get("/admin/candidate/{candidate_id}")
async def admin_candidate_detail(candidate_id: str):
    """Full recruiter view of a single candidate. Returns:
      - candidate record (name, email, cv_url, role_id, workflow_id, instance_id)
      - workflow (phase, status, awaiting_reason, type, jurisdiction)
      - agent_outputs (cv_crystalliser profile + component_spec + inconsistencies,
        screening verdict, etc.)
      - voice_transcript turns
      - active magic-link scopes
      - audit ledger entries from the workflow
      - phase event timeline
    """
    candidate = app_state.store.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(404, "candidate not found")
    wf = app_state.store.get_workflow(candidate.get("workflow_id", ""))
    if wf is None:
        raise HTTPException(404, "workflow not found")

    active_tokens = [
        {"scope": t["scope"], "token": t["token"], "expires_at": t["expires_at"]}
        for t in app_state.magic_links.list_active()
        if t["candidate_id"] == candidate_id
    ]

    return {
        "candidate": candidate,
        "workflow": {
            "id": wf.id,
            "type": wf.type,
            "phase": wf.current_phase,
            "status": wf.status,
            "jurisdiction": wf.jurisdiction,
            "metadata": wf.metadata or {},
            "awaiting_reason": (wf.metadata or {}).get("awaiting_reason"),
        },
        "agent_outputs": getattr(wf, "agent_outputs", {}) or {},
        # Real LLM reasoning trace from the agent-tracked-executor wrapper.
        # Each entry: agent_label, phase, started_at, completed_at, messages,
        # tool_calls, extracted_json, latency_ms, tokens_in/out. Empty when
        # the workflow has only run stub-path agents (no LLM calls).
        "agent_reasoning": app_state.store.get_agent_reasoning(wf.id),
        "voice_transcript": candidate.get("voice_transcript", []),
        "active_tokens": active_tokens,
        "action_ledger": [
            {
                "action": a.action,
                "actor_kind": getattr(a, "actor_kind", getattr(a, "actorKind", "")),
                "actor_id": getattr(a, "actor_id", getattr(a, "actorId", "")),
                "timestamp": a.timestamp,
                "details": getattr(a, "details", {}),
            }
            for a in (getattr(wf, "action_ledger", None) or [])
        ],
        "phase_events": [
            {
                "phase": getattr(p, "phase", "") or p.get("phase", "") if isinstance(p, dict) else getattr(p, "phase", ""),
                "event": getattr(p, "event", "") or p.get("event", "") if isinstance(p, dict) else getattr(p, "event", ""),
                "timestamp": getattr(p, "timestamp", 0) or p.get("timestamp", 0) if isinstance(p, dict) else getattr(p, "timestamp", 0),
                "summary": getattr(p, "summary", "") or p.get("summary", "") if isinstance(p, dict) else getattr(p, "summary", ""),
            }
            for p in (getattr(wf, "phase_events", None) or [])
        ],
    }
