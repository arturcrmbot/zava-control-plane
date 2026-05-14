"""Recruiter-side decision endpoints for the two operator-review HITL gates
in Phase 7 (Interview).

  POST /api/portal/admin/candidate/{candidate_id}/interview-invite
       Resumes the orchestrator's `awaiting_interview_invite` wait by
       raising `interview_invite` with body {decision: invite|reject, ...}.

  POST /api/portal/admin/candidate/{candidate_id}/post-interview-decision
       Resumes `awaiting_interview_complete` by raising `offer_decision`
       with the recruiter's notes + rating + level + decision.

Both endpoints are mounted off /api/portal/admin to mirror the existing
admin-only candidate endpoints. No auth at this layer — the recruiter
view is a private surface in the demo. Engagement-POC hardens this with
real auth.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.server.services.durable_client import raise_orchestration_event
from api.server.state import app_state

router = APIRouter(prefix="/api/portal/admin", tags=["portal", "admin"])


class InterviewInviteRequest(BaseModel):
    decision: str  # "invite" | "reject"
    reason: str | None = None
    resolved_by: str | None = None


@router.post("/candidate/{candidate_id}/interview-invite")
async def interview_invite(candidate_id: str, body: InterviewInviteRequest):
    decision = body.decision.lower()
    if decision not in {"invite", "reject"}:
        raise HTTPException(400, "decision must be invite|reject")
    cand = app_state.store.get_candidate(candidate_id)
    if cand is None:
        raise HTTPException(404, "candidate not found")
    instance_id = cand.get("instance_id")
    if not instance_id:
        raise HTTPException(409, "candidate has no orchestration instance")

    payload = {
        "candidate_id": candidate_id,
        "decision": decision,
        "resolved_by": body.resolved_by or "recruiter",
        "reason": body.reason,
    }
    await raise_orchestration_event(instance_id, "interview_invite", payload)
    return {"ok": True, "decision": decision}


class PostInterviewRequest(BaseModel):
    # NOTE: rating is unconstrained at the Pydantic layer so we can return a
    # 400 (with a clear "rating must be 1..5" message) instead of FastAPI's
    # default 422 envelope. The spec test pins the status to 400.
    decision: str  # "offer" | "reject"
    notes: str = ""
    rating: int
    level: str | None = None
    resolved_by: str | None = None


@router.post("/candidate/{candidate_id}/post-interview-decision")
async def post_interview_decision(candidate_id: str, body: PostInterviewRequest):
    decision = body.decision.lower()
    if decision not in {"offer", "reject"}:
        raise HTTPException(400, "decision must be offer|reject")
    if not 1 <= body.rating <= 5:
        raise HTTPException(400, "rating must be 1..5")
    if decision == "offer" and not body.level:
        raise HTTPException(400, "level is required when decision is offer")
    cand = app_state.store.get_candidate(candidate_id)
    if cand is None:
        raise HTTPException(404, "candidate not found")
    instance_id = cand.get("instance_id")
    if not instance_id:
        raise HTTPException(409, "candidate has no orchestration instance")

    # Stash the recruiter's notes/rating on the candidate record so the
    # recruiter view can show them after submission. The orchestrator also
    # gets them via the event payload below for the action ledger.
    cand["interview_notes"] = body.notes
    cand["interview_rating"] = body.rating
    cand["interview_decision"] = decision
    if body.level:
        cand["interview_level"] = body.level
    app_state.store.upsert_candidate(cand)

    payload = {
        "candidate_id": candidate_id,
        "decision": decision,
        "level": body.level,
        "notes": body.notes,
        "rating": body.rating,
        "resolved_by": body.resolved_by or "recruiter",
    }
    await raise_orchestration_event(instance_id, "offer_decision", payload)
    return {"ok": True, "decision": decision}
