"""Candidate-side interview-booking routes.

Two endpoints, both gated by a `book_interview`-scope magic-link token:

  GET  /api/portal/interview/resolve?token=...
       Peeks the token, returns candidate id + role title + the deterministic
       5x3 slot grid. Drives the /book?token=... page in the candidate portal.

  POST /api/portal/interview/book
       Consumes the token, persists the chosen slot on the candidate dict,
       raises `interview_booked` on the underlying Durable instance so the
       orchestrator resumes from awaiting_interview_booking.
"""
from __future__ import annotations
import hashlib
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.server.services.durable_client import raise_orchestration_event
from api.server.services.magic_link import (
    MagicLinkAlreadyConsumed,
    MagicLinkExpired,
)
from api.server.state import app_state

router = APIRouter(prefix="/api/portal/interview", tags=["portal", "interview"])

_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri"]
_TIME_KEYS = ["09:00", "13:00", "16:00"]


def _slot_grid_for(candidate_id: str) -> list[dict]:
    """Build a deterministic 5x3 mock calendar starting next Monday.

    `available` is True for ~80% of slots, deterministic per-candidate so the
    same candidate sees the same pattern across page refreshes. Past dates
    (rare - only matters if the request lands on Monday before midnight) are
    always unavailable.
    """
    today = date.today()
    # Monday of next week - keeps the demo calendar always-future.
    days_until_monday = (7 - today.weekday()) % 7 or 7
    start = today + timedelta(days=days_until_monday)
    out: list[dict] = []
    for d_idx, day_key in enumerate(_DAY_KEYS):
        the_date = start + timedelta(days=d_idx)
        for t in _TIME_KEYS:
            slot_id = f"{day_key}-{t}"
            digest = hashlib.sha256(f"{candidate_id}:{slot_id}".encode()).hexdigest()
            available = int(digest, 16) % 5 != 0  # ~80% true
            starts_at = datetime.combine(
                the_date, datetime.strptime(t, "%H:%M").time(),
            ).isoformat()
            out.append({
                "slot_id": slot_id,
                "label": f"{the_date.strftime('%a %d %b')} · {t}",
                "starts_at": starts_at,
                "available": available,
            })
    return out


@router.get("/resolve")
async def resolve(token: str):
    """Peek the booking token - does not consume."""
    try:
        payload = app_state.magic_links.peek(token, scope="book_interview")
    except MagicLinkExpired:
        raise HTTPException(410, "link expired")
    except ValueError:
        # Wrong scope - surface as 404 so we don't leak token existence.
        raise HTTPException(404, "invalid token")
    if payload is None:
        raise HTTPException(404, "invalid token")
    cand = app_state.store.get_candidate(payload["candidate_id"])
    if cand is None:
        raise HTTPException(404, "candidate not found")
    workflow = app_state.store.get_workflow(cand.get("workflow_id", ""))
    role_title = (workflow.metadata if workflow else {}).get("role_title") if workflow else None
    return {
        "candidate_id": cand["id"],
        "role_title": role_title or cand.get("metadata_role_title") or "the role",
        "slots": _slot_grid_for(cand["id"]),
    }


class BookRequest(BaseModel):
    token: str
    slot_id: str


@router.post("/book")
async def book(body: BookRequest):
    """Consume token + raise interview_booked on the Durable instance."""
    grid_ids = {f"{d}-{t}" for d in _DAY_KEYS for t in _TIME_KEYS}
    if body.slot_id not in grid_ids:
        raise HTTPException(400, "unknown slot_id")
    try:
        payload = app_state.magic_links.consume(body.token, scope="book_interview")
    except MagicLinkAlreadyConsumed:
        raise HTTPException(409, "already booked")
    except MagicLinkExpired:
        raise HTTPException(410, "link expired")
    except ValueError:
        raise HTTPException(404, "invalid token")
    cand = app_state.store.get_candidate(payload["candidate_id"])
    if cand is None:
        raise HTTPException(404, "candidate not found")
    instance_id = cand.get("instance_id")
    if not instance_id:
        raise HTTPException(409, "candidate has no orchestration instance")

    # Resolve the chosen slot's full record from the deterministic grid so we
    # have starts_at / label (the form only sends slot_id).
    full_slot = next(
        (s for s in _slot_grid_for(cand["id"]) if s["slot_id"] == body.slot_id),
        {"slot_id": body.slot_id},
    )
    cand["interview_slot"] = full_slot
    app_state.store.upsert_candidate(cand)

    await raise_orchestration_event(instance_id, "interview_booked", {
        "candidate_id": cand["id"],
        "slot": full_slot,
    })
    return {"ok": True}
