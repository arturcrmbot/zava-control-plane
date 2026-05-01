"""Candidate-portal voice screen — native WebRTC bridge to Azure GPT-Realtime.

Five routes:

  GET  /api/portal/voice/screen-resolve?token=...
       Peeks a `screen`-scope magic-link token without consuming it. The
       portal's /screen page calls this on mount so it can hand the
       candidate id to the WebRTC client.

  POST /api/portal/voice/session
       Mints an ephemeral key for an Azure GPT-Realtime session. Browser
       calls this once before opening the WebRTC peer connection. We hold
       the long-lived Azure credential server-side; the browser only ever
       sees a short-lived ephemeral key.

  POST /api/portal/voice/rtc
       Proxies the browser's SDP offer to Azure's WebRTC endpoint and
       returns Azure's SDP answer. Two reasons we do not let the browser
       call Azure directly: (1) avoids a CORS preflight against the Azure
       endpoint; (2) keeps the ephemeral-key short-lived header off the
       browser-side fetch.

  POST /api/portal/voice/{candidate_id}/transcript
       Browser-side callback after the call ends. Validates the screen
       token, persists the transcript turns on the candidate record, and
       raises the `voice_complete` external event on the Durable
       orchestration so Phase 6 resumes with the score.

  POST /api/portal/voice/{candidate_id}/canned
       Demo-mode fallback when VOICE_TRANSPORT=canned — replays a static
       transcript through the same `voice_complete` resume path.

See `docs/superpowers/plans/2026-04-30-voice-real-plan.md` for the design
and `C:\\dev\\firstcentral\\voice-direct\\server.py` for the original
WebRTC bridge this module mirrors.
"""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from api.server.services.durable_client import raise_orchestration_event
from api.server.services.magic_link import (
    MagicLinkAlreadyConsumed,
    MagicLinkExpired,
)
from api.server.state import app_state
from api.shared.events import FleetEvent

router = APIRouter(prefix="/api/portal/voice", tags=["portal", "voice"])


def _portal_status_url_for(candidate_id: str) -> str | None:
    """Look up the candidate's most recent active status-scope token and
    return the full /portal?token=... URL, or None if no active status link
    exists. Used by the post-call endpoints so the candidate can be returned
    to a working portal page (their original screen token has just been
    consumed and is wrong-scope for /portal anyway)."""
    base = os.getenv("PORTAL_BASE_URL", "http://localhost:5174")
    rows = app_state.magic_links.list_active()
    matches = [r for r in rows if r.get("candidate_id") == candidate_id and r.get("scope") == "status"]
    if not matches:
        return None
    matches.sort(key=lambda r: r.get("issued_at") or 0, reverse=True)
    return f"{base}/portal?token={matches[0]['token']}"


# ---------------------------------------------------------------- WebRTC config


_REALTIME_SESSION_URL = (os.environ.get("AZURE_GPT_REALTIME_URL") or "").strip('"')
_WEBRTC_URL = (os.environ.get("WEBRTC_URL") or "").strip('"')
_REALTIME_DEPLOYMENT = (
    os.environ.get("AZURE_GPT_REALTIME_DEPLOYMENT") or "gpt-realtime-1.5"
).strip('"')
_REALTIME_KEY = (os.environ.get("AZURE_GPT_REALTIME_KEY") or "").strip('"')
_REALTIME_VOICE = (os.environ.get("AZURE_REALTIME_VOICE") or "alloy").strip('"')


async def _realtime_auth_headers() -> dict[str, str]:
    """Auth header for the Azure GPT-Realtime control plane.

    Prefer the API key (cheaper, no token-cache eviction surprises). Fall back
    to DefaultAzureCredential when key isn't set — matches the firstcentral
    accelerator's pattern.
    """
    if _REALTIME_KEY:
        return {"api-key": _REALTIME_KEY, "Content-Type": "application/json"}
    from azure.identity.aio import DefaultAzureCredential
    cred = DefaultAzureCredential()
    try:
        token = await cred.get_token("https://cognitiveservices.azure.com/.default")
        return {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        }
    finally:
        await cred.close()


class SessionResponse(BaseModel):
    ephemeral_key: str
    webrtc_url: str
    deployment: str
    voice: str


@router.post("/session", response_model=SessionResponse)
async def create_session():
    """Mint an ephemeral GPT-Realtime session key for the browser."""
    if not _REALTIME_SESSION_URL or not _WEBRTC_URL:
        raise HTTPException(
            500, "AZURE_GPT_REALTIME_URL and WEBRTC_URL must be set",
        )
    headers = await _realtime_auth_headers()
    payload = {"model": _REALTIME_DEPLOYMENT, "voice": _REALTIME_VOICE}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_REALTIME_SESSION_URL, headers=headers, json=payload)
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Realtime session error: {resp.text}")
    return SessionResponse(
        ephemeral_key=resp.json()["client_secret"]["value"],
        webrtc_url=_WEBRTC_URL,
        deployment=_REALTIME_DEPLOYMENT,
        voice=_REALTIME_VOICE,
    )


@router.post("/rtc")
async def proxy_rtc(request: Request):
    """Proxy the browser's SDP offer to Azure WebRTC; return Azure's answer."""
    body = await request.body()
    eph_key = request.headers.get("authorization", "").replace("Bearer ", "").strip()
    if not eph_key:
        raise HTTPException(401, "missing Bearer ephemeral key")
    url = f"{_WEBRTC_URL}?model={_REALTIME_DEPLOYMENT}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, content=body, headers={
            "Authorization": f"Bearer {eph_key}",
            "Content-Type": "application/sdp",
        })
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.text)
    return Response(
        content=resp.content,
        media_type="application/sdp",
        status_code=resp.status_code,
    )


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
    # Pass the full transcript through the event payload — the Phase 7
    # interview-recommender reads it via voice_payload.transcript. The
    # worker process can't see FastAPI's in-memory candidate store so the
    # transcript MUST travel via the event (not the candidate dict).
    transcript_dicts = [t.model_dump() for t in body.transcript]
    await raise_orchestration_event(instance_id, "voice_complete", {
        "candidate_id": candidate_id,
        "score": body.score,
        "duration_s": body.duration_s,
        "turn_count": len(body.transcript),
        "transcript": transcript_dicts,
    })
    return {"ok": True, "portal_url": _portal_status_url_for(candidate_id)}


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
        "transcript": canned,
    })
    return {"ok": True, "source": "canned", "portal_url": _portal_status_url_for(candidate_id)}
