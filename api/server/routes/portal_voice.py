"""Accelerator -> FastAPI callback after a voice screen call ends.

Two routes:

  GET  /api/portal/voice/screen-resolve?token=...
       Peeks a `screen`-scope magic-link token without consuming it. The
       portal's /screen page calls this on mount so it can hand the
       candidate id to the embedded accelerator iframe. Returns
         200 {candidate_id}
         404 if the token is unknown or scope-mismatched
         410 if the token is past its expiry

  POST /api/portal/voice/{candidate_id}/transcript
       Final webhook from the accelerator (or its iframe parent) once the
       call ends. Validates the screen token, persists the transcript on
       the candidate record, and raises the `voice_complete` external
       event on the Durable orchestration so Phase 6 of the
       HiringOrchestrator resumes with the score.

       Body:
         { token, transcript: [{role, text, ts}, ...], score, duration_s }
       Returns:
         200 {ok: true}
         403 on invalid / scope-mismatched / candidate-mismatched token
         404 on unknown candidate
         409 if the candidate has no orchestration instance yet

See `docs/superpowers/plans/2026-04-30-voice-real-plan.md` Phase 1 Tasks 1-2.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.server.services.durable_client import raise_orchestration_event
from api.server.services.magic_link import (
    MagicLinkAlreadyConsumed,
    MagicLinkExpired,
)
from api.server.state import app_state
from api.shared.events import FleetEvent

router = APIRouter(prefix="/api/portal/voice", tags=["portal", "voice"])


# ---------------------------------------------------------------- screen-resolve


@router.get("/screen-resolve")
async def screen_resolve(token: str):
    """Peek a `screen`-scope token and return the candidate id.

    Used by the portal's /screen page to feed the accelerator iframe its
    `candidate_id` query param. Token is NOT consumed — the candidate is
    about to redeem it via the /transcript callback when the call ends.
    """
    try:
        row = app_state.magic_links.peek(token, scope="screen")
    except MagicLinkExpired:
        raise HTTPException(410, "token expired")
    except ValueError:
        # Scope mismatch or other validation failure — surface as 404 so we
        # don't leak whether the token exists under a different scope.
        raise HTTPException(404, "token not found")
    if row is None:
        raise HTTPException(404, "token not found")
    return {"candidate_id": row["candidate_id"]}


# ---------------------------------------------------------------- /transcript


class TranscriptTurn(BaseModel):
    role: str       # "agent" | "candidate"
    text: str
    ts: float


class TranscriptPayload(BaseModel):
    token: str
    transcript: list[TranscriptTurn]
    score: float
    duration_s: float


@router.post("/{candidate_id}/transcript")
async def receive_transcript(candidate_id: str, body: TranscriptPayload):
    # Validate the screen token. consume() enforces single-use on screen-scope
    # tokens (issued single_use=True) so a transcript callback can fire only
    # once per issued link.
    try:
        payload = app_state.magic_links.consume(body.token, scope="screen")
    except (MagicLinkExpired, MagicLinkAlreadyConsumed, ValueError):
        raise HTTPException(403, "invalid token")
    if payload["candidate_id"] != candidate_id:
        raise HTTPException(403, "token/candidate mismatch")

    candidate = app_state.store.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(404, "unknown candidate")
    instance_id = candidate.get("instance_id")
    if not instance_id:
        raise HTTPException(409, "candidate has no orchestration instance")

    # Persist transcript on the candidate record so /status can replay the
    # conversation. append_voice_transcript is per-turn so iterate.
    for turn in body.transcript:
        app_state.store.append_voice_transcript(candidate_id, turn.model_dump())

    # Surface the callback on the bus so the Control Plane / audit log picks
    # it up alongside other portal events.
    app_state.bus.emit(FleetEvent(
        type="voice_transcript.received",
        workflow_id=candidate.get("workflow_id"),
        candidate_id=candidate_id,
        score=body.score,
        duration_s=body.duration_s,
        turn_count=len(body.transcript),
    ))

    # Resume the suspended Phase 6 orchestration. The voice_graph in
    # api/functions/workflows/hiring.py awaits "voice_complete" on a
    # 24h timer race — see plan §Phase 1 Task 2.
    await raise_orchestration_event(instance_id, "voice_complete", {
        "candidate_id": candidate_id,
        "score": body.score,
        "duration_s": body.duration_s,
        "turn_count": len(body.transcript),
    })
    return {"ok": True}


# ---------------------------------------------------------------- /canned-screen
# Demo-mode fallback for `VOICE_TRANSPORT=canned`. The portal's /screen page
# checks this transport at mount time and renders a "Run canned screen" button
# instead of the accelerator iframe; that button POSTs here, we replay the
# existing acs-mcp mock's canned transcript shape, and the orchestration
# resumes through the same code path. Keeps the demo robust if the
# accelerator host is offline.


@router.post("/{candidate_id}/canned")
async def canned_screen(candidate_id: str, token: str):
    if (os.getenv("VOICE_TRANSPORT", "accelerator") or "").lower() != "canned":
        raise HTTPException(409, "canned transport disabled")

    # Reuse the same single-use semantics as the real path.
    try:
        payload = app_state.magic_links.consume(token, scope="screen")
    except (MagicLinkExpired, MagicLinkAlreadyConsumed, ValueError):
        raise HTTPException(403, "invalid token")
    if payload["candidate_id"] != candidate_id:
        raise HTTPException(403, "token/candidate mismatch")

    candidate = app_state.store.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(404, "unknown candidate")
    instance_id = candidate.get("instance_id")
    if not instance_id:
        raise HTTPException(409, "candidate has no orchestration instance")

    # Static canned transcript matching the acs-mcp mock shape.
    canned = [
        {"role": "agent", "text": "Hi, thanks for taking the call.", "ts": 0.0},
        {"role": "candidate", "text": "Happy to chat.", "ts": 2.5},
        {"role": "agent", "text": "Tell me about your last project.", "ts": 4.0},
        {"role": "candidate", "text": "I shipped a Durable Functions pipeline.", "ts": 6.0},
    ]
    for turn in canned:
        app_state.store.append_voice_transcript(candidate_id, turn)

    await raise_orchestration_event(instance_id, "voice_complete", {
        "candidate_id": candidate_id,
        "score": 7.0,
        "duration_s": 60.0,
        "turn_count": len(canned),
        "source": "canned",
    })
    return {"ok": True, "source": "canned"}
