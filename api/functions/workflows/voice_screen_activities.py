"""Phase 6 voice-screen activities (link issuance + email delivery).

Lives in its own module so it can be imported without dragging in the
agent-framework graph machinery (`api.functions.graphs.*`) that activities.py
hauls in via its eager imports. The two activities here only depend on
`app_state` from the FastAPI side and on the email/magic-link services —
keeping them isolated lets the unit tests exercise them without spinning
up the whole graph stack.

Both functions are re-exported from `api.functions.workflows.activities`
for backwards compatibility with the function_app.py registration.
"""
from __future__ import annotations
import os


def issue_screen_link_activity(payload: dict) -> dict:
    """Mint a `screen`-scope magic-link token for the candidate.

    Called from the HiringOrchestrator before it suspends on
    `voice_complete`. The token gates the /screen page (peek-only) and the
    /transcript callback (single-use consume) so a candidate can complete
    the screening call exactly once per issuance.

    Returns {"token": ..., "candidate_id": ..., "portal_url": ...} so the
    sibling activity (`send_screen_email_activity`) can compose the email
    body without another store lookup.
    """
    from api.server.state import app_state

    candidate_id = payload["candidate_id"]
    ttl_seconds = int(payload.get("ttl_seconds") or 24 * 3600)
    token = app_state.magic_links.issue(
        candidate_id=candidate_id,
        scope="screen",
        ttl_seconds=ttl_seconds,
        single_use=True,
    )
    base = os.getenv("PORTAL_BASE_URL", "http://localhost:5274").rstrip("/")
    return {
        "token": token,
        "candidate_id": candidate_id,
        "portal_url": f"{base}/screen?token={token}",
    }


def send_screen_email_activity(payload: dict) -> dict:
    """Email the candidate the /screen?token=... call link.

    Mirrors `portal_orchestration.make_handler` email shape: use
    `app_state.email_sender` (real ACS Email when configured, outbox-only
    fallback otherwise). Always best-effort — a send failure must not
    abort the orchestration since the candidate can be sent the link
    via the admin Candidates panel as a fallback.
    """
    from api.server.services.email_send import EmailSendError
    from api.server.state import app_state

    candidate_id = payload["candidate_id"]
    token = payload["token"]
    portal_url = payload.get("portal_url")
    candidate = app_state.store.get_candidate(candidate_id)
    if candidate is None:
        return {"sent": False, "reason": "unknown_candidate"}

    if not portal_url:
        base = os.getenv("PORTAL_BASE_URL", "http://localhost:5274").rstrip("/")
        portal_url = f"{base}/screen?token={token}"

    name = candidate.get("name") or "there"
    subject = "Your screening call is ready"
    html = (
        f"<p>Hi {name},</p>"
        f"<p>Your screening call is ready. "
        f"<a href=\"{portal_url}\">Start the call</a> when you're ready — "
        f"the link works once and expires after 24 hours.</p>"
        f"<p>Thanks,<br/>Zava Talent</p>"
    )
    try:
        message_id = app_state.email_sender.send(
            to=candidate.get("email") or "unknown@example.com",
            subject=subject,
            html_body=html,
            candidate_id=candidate_id,
        )
    except EmailSendError as exc:  # pragma: no cover — surfaces in logs
        return {"sent": False, "reason": str(exc)}

    return {"sent": True, "message_id": message_id, "portal_url": portal_url}
