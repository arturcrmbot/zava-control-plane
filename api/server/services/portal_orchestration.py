"""Portal orchestration glue — subscribes the candidate-portal flow to the
event bus so the right sequence of side effects (issue magic link, send
shortlist email) follows from agent completions inside the hiring workflow.

The candidate portal does not own the Triage / cv_crystalliser graph (that
lives under `api/functions/graphs/triage.py` and is owned by the AG-UI
subagent). We subscribe to the `agent.completed` event the wrapper emits
once the cv_crystalliser run lands, and react in this process — keeping the
portal-specific concerns out of the agent executor itself.

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 8.
"""
from __future__ import annotations

import os
from html import escape
from typing import Callable

from api.server.services.email_send import EmailSendError
from api.shared.events import FleetEvent

# Default threshold mirrors the plan: anything at-or-above 0.5 is shortlisted.
# Override via SHORTLIST_THRESHOLD for tuning runs.
_DEFAULT_THRESHOLD = 0.5

# Status-scope magic-link TTL — 7 days so the candidate can come back after
# a screening, interview, etc.
_STATUS_LINK_TTL_SECONDS = 7 * 24 * 3600


def _shortlist_threshold() -> float:
    raw = os.getenv("SHORTLIST_THRESHOLD")
    if raw is None:
        return _DEFAULT_THRESHOLD
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_THRESHOLD


def _portal_base_url() -> str:
    return os.getenv("PORTAL_BASE_URL", "http://localhost:5174")


def _extract_score(event: FleetEvent) -> float:
    """Extract a 0..1 shortlist score from an agent.completed event payload.

    cv_crystalliser doesn't itself emit a `shortlist_score` field today —
    when it's missing we treat the candidate as shortlisted (score=1.0) so
    the demo flow always proceeds. A real triage agent would populate
    `extracted_json.shortlist_score` directly.
    """
    extra = event.model_dump()
    extracted = extra.get("extracted_json") or {}
    if not isinstance(extracted, dict):
        return 1.0
    for key in ("shortlist_score", "score", "fit_score"):
        v = extracted.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return 1.0


def _render_magic_link_email(name: str, portal_url: str) -> tuple[str, str]:
    """Return (subject, html_body) for the shortlist invite email."""
    safe_name = escape(name or "there")
    safe_url = escape(portal_url, quote=True)
    subject = "Your application — next steps"
    body = (
        "<!doctype html><html><body style=\"font-family: system-ui, sans-serif;\">"
        f"<p>Hi {safe_name},</p>"
        "<p>Thanks for applying. We'd love to take the next step with you.</p>"
        f"<p><a href=\"{safe_url}\">Open your candidate portal</a> to schedule "
        "your screening conversation.</p>"
        "<p>This link is personal to you and good for seven days.</p>"
        "<p>— Talent Acquisition</p>"
        "</body></html>"
    )
    return subject, body


def make_handler(app_state) -> Callable[[FleetEvent], None]:
    """Build a bus handler closed over `app_state`. Returned callable is
    safe to pass to `EventBus.on('agent.completed', ...)`. The handler is
    a no-op for events that aren't from the cv_crystalliser, or for
    workflows whose candidate is unknown."""

    threshold = _shortlist_threshold()

    def _handler(event: FleetEvent) -> None:
        if event.type != "agent.completed":
            return
        extra = event.model_dump()
        if extra.get("agent_label") != "cv_crystalliser":
            return

        score = _extract_score(event)
        if score < threshold:
            return

        workflow_id = event.workflow_id
        if not workflow_id:
            return
        workflow = app_state.store.get_workflow(workflow_id)
        if workflow is None:
            return
        candidate_id = (
            extra.get("candidate_id")
            or (workflow.metadata or {}).get("candidate_id")
        )
        if not candidate_id:
            return
        candidate = app_state.store.get_candidate(candidate_id)
        if candidate is None:
            return

        # Issue a long-lived, repeatable status-scope link so the candidate
        # can revisit the portal across the hiring lifecycle.
        token = app_state.magic_links.issue(
            candidate_id=candidate_id,
            scope="status",
            ttl_seconds=_STATUS_LINK_TTL_SECONDS,
            single_use=False,
        )

        portal_url = f"{_portal_base_url()}/portal?token={token}"
        subject, html = _render_magic_link_email(
            name=candidate.get("name") or "there",
            portal_url=portal_url,
        )

        try:
            app_state.email_sender.send(
                to=candidate.get("email") or "unknown@example.com",
                subject=subject,
                html_body=html,
            )
        except EmailSendError as exc:  # pragma: no cover — surfaces in logs
            print(f"[portal] shortlist email send failed: {exc}")

        # Surface the issuance on the bus so the Control Plane / audit log
        # picks it up. Ordered last so the email send is on the critical path.
        app_state.bus.emit(FleetEvent(
            type="magic_link.issued",
            workflow_id=workflow_id,
            candidate_id=candidate_id,
            magic_token=token,
            portal_url=portal_url,
            scope="status",
        ))

    return _handler


def attach(app_state) -> Callable[[], None]:
    """Subscribe the cv_crystalliser handler to the bus. Returns the
    unsubscribe callable so the lifespan teardown can detach cleanly."""
    handler = make_handler(app_state)
    return app_state.bus.on("agent.completed", handler)
