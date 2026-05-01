"""Phase 7 (Interview) sub-wait activities — runs alongside the existing
voice_screen_activities. Keeping these in their own module so the unit
tests don't pull in the agent-framework graph machinery.

Four activities, all imported and re-exported by activities.py:

  - hiring_interview_recommender_activity — runs the recommender agent at
    gates `post_voice` and `post_interview`.
  - issue_book_interview_link_activity   — mints book_interview scope token.
  - send_book_interview_email_activity   — emails candidate the /book URL.
  - send_rejection_email_activity        — auto-rejection at either reject gate.
"""
from __future__ import annotations
import asyncio
import os

from api.server.services.email_send import EmailSendError


def _portal_base() -> str:
    return os.getenv("PORTAL_BASE_URL", "http://localhost:5174").rstrip("/")


def hiring_interview_recommender_activity(payload: dict) -> dict:
    """Run the interview-recommender executor inside the Functions worker.

    Mirrors hiring_*_activity wrappers — synchronous entry-point that
    `asyncio.run`s the async agent call. Returns whatever the executor
    returned so the orchestrator can stash it on `enriched`.
    """
    from api.functions.graphs.executors.agents import agent_interview_recommender
    return asyncio.run(agent_interview_recommender.execute(payload))


def issue_book_interview_link_activity(payload: dict) -> dict:
    """Mint a `book_interview` scope token for the candidate (single-use, 7d).

    Called from the orchestrator after the recruiter clicks Invite at gate 1.
    Returns {token, candidate_id, portal_url} so the sibling email activity
    can compose the body without another store lookup.
    """
    from api.server.state import app_state
    candidate_id = payload["candidate_id"]
    ttl_seconds = int(payload.get("ttl_seconds") or 7 * 24 * 3600)
    token = app_state.magic_links.issue(
        candidate_id=candidate_id,
        scope="book_interview",
        ttl_seconds=ttl_seconds,
        single_use=True,
    )
    return {
        "token": token,
        "candidate_id": candidate_id,
        "portal_url": f"{_portal_base()}/book?token={token}",
    }


def send_book_interview_email_activity(payload: dict) -> dict:
    """Email the candidate the /book?token=… interview-booking link.

    Best-effort — a send failure must not abort the orchestration since
    the recruiter can copy/paste the link from the recruiter view.

    Reads candidate name/email from the payload first (orchestrator passes
    them through `enriched["candidate"]`); falls back to the local store
    for backwards compatibility, but the worker process's StateStore is
    independent of FastAPI's, so the payload path is the load-bearing one.
    """
    from api.server.state import app_state
    candidate_id = payload["candidate_id"]
    token = payload["token"]
    role_title = payload.get("role_title") or "the role"
    portal_url = payload.get("portal_url") or f"{_portal_base()}/book?token={token}"
    name = payload.get("name")
    email = payload.get("email")
    if not name or not email:
        candidate = app_state.store.get_candidate(candidate_id)
        if candidate is None and (not name or not email):
            return {"sent": False, "reason": "unknown_candidate"}
        if candidate:
            name = name or candidate.get("name")
            email = email or candidate.get("email")
    name = name or "there"
    subject = f"Schedule your {role_title} interview"
    html = (
        f"<p>Hi {name},</p>"
        f"<p>Great news — we'd like to invite you to a full interview for "
        f"the <strong>{role_title}</strong> role.</p>"
        f"<p><a href=\"{portal_url}\">Pick a time that works for you</a> "
        f"— the link works once and expires after 7 days.</p>"
        f"<p>Thanks,<br/>WPP Talent</p>"
    )
    try:
        msg_id = app_state.email_sender.send(
            to=email or "unknown@example.com",
            subject=subject,
            html_body=html,
        )
    except EmailSendError as exc:  # pragma: no cover
        return {"sent": False, "reason": str(exc)}
    return {"sent": True, "message_id": msg_id, "portal_url": portal_url}


def send_rejection_email_activity(payload: dict) -> dict:
    """Polite auto-rejection email used at both recruiter reject gates.

    `gate` ∈ {"interview", "offer"} only differs in one sentence of body
    copy. We never include the recruiter's free-text reason in the email
    — keeps us out of trouble re: feedback the candidate could quote.
    """
    from api.server.state import app_state
    candidate_id = payload["candidate_id"]
    gate = (payload.get("gate") or "interview").lower()
    role_title = payload.get("role_title") or "the role"
    name = payload.get("name")
    email = payload.get("email")
    if not name or not email:
        candidate = app_state.store.get_candidate(candidate_id)
        if candidate is None and (not name or not email):
            return {"sent": False, "reason": "unknown_candidate"}
        if candidate:
            name = name or candidate.get("name")
            email = email or candidate.get("email")
    name = name or "there"
    if gate == "offer":
        bridge = (
            f"After the interview stage we've decided not to move forward "
            f"with the <strong>{role_title}</strong> role at this time."
        )
    else:
        bridge = (
            f"After reviewing your screening for the "
            f"<strong>{role_title}</strong> role, we've decided not to "
            f"move forward at this stage."
        )
    subject = f"Update on your {role_title} application"
    html = (
        f"<p>Hi {name},</p>"
        f"<p>Thanks for taking the time to interview with us. {bridge}</p>"
        f"<p>We'll keep your details on file and be in touch if a better "
        f"fit opens up.</p>"
        f"<p>Best,<br/>WPP Talent</p>"
    )
    try:
        msg_id = app_state.email_sender.send(
            to=email or "unknown@example.com",
            subject=subject,
            html_body=html,
        )
    except EmailSendError as exc:  # pragma: no cover
        return {"sent": False, "reason": str(exc)}
    return {"sent": True, "message_id": msg_id, "gate": gate}
