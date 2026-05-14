"""Portal orchestration glue — subscribes the candidate-portal flow to the
event bus so the right sequence of side effects follows from candidate-side
events. Two subscriptions:

  candidate.applied (from /api/portal/apply)
    -> spawn a fresh HiringOrchestrator Durable instance for this candidate,
       record the instance_id on the candidate record, and auto-approve
       the Finance-BP budget HITL so the workflow advances to Triage.

  agent.completed (from cv_crystalliser via the agent-tracked-executor)
    -> issue a status-scope magic-link token, send the shortlist email,
       emit magic_link.issued.

The candidate portal does not own the Triage / cv_crystalliser graph (that
lives under `api/functions/graphs/triage.py`) — we subscribe to its events
instead.

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 8.
"""
from __future__ import annotations

import asyncio
import os
from html import escape
from typing import Callable

from api.server.services.durable_client import (
    raise_orchestration_event,
    schedule_new_orchestration,
)
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
    return os.getenv("PORTAL_BASE_URL", "http://localhost:5274")


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
                candidate_id=candidate_id,
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


async def _spawn_hire_orchestration(app_state, *, candidate_id: str, workflow_id: str, role_id: str) -> None:
    """Issue the candidate's status-scope magic link + email immediately, then
    try to start a HiringOrchestrator Durable instance and auto-approve the
    Finance-BP budget HITL. The status link issuance is on a separate path
    from the orchestration spawn so the candidate ALWAYS gets a live /portal
    URL — even if the Functions host is down (devmode), they can still see
    "Application received, phase=Applied" and resume once the host comes up.
    """
    candidate = app_state.store.get_candidate(candidate_id)
    if candidate is None:
        return
    workflow = app_state.store.get_workflow(workflow_id)

    # Step 1 (always runs): mint status-scope token + send acknowledgement email.
    try:
        status_token = app_state.magic_links.issue(
            candidate_id=candidate_id,
            scope="status",
            ttl_seconds=_STATUS_LINK_TTL_SECONDS,
            single_use=False,
        )
        portal_url = f"{_portal_base_url()}/portal?token={status_token}"
        subject, html = _render_magic_link_email(
            name=candidate.get("name") or "there",
            portal_url=portal_url,
        )
        try:
            app_state.email_sender.send(
                to=candidate.get("email") or "unknown@example.com",
                subject=subject,
                html_body=html,
                candidate_id=candidate_id,
            )
        except EmailSendError as exc:  # pragma: no cover
            print(f"[portal] application-received email send failed: {exc}")
        app_state.bus.emit(FleetEvent(
            type="magic_link.issued",
            workflow_id=workflow_id,
            candidate_id=candidate_id,
            magic_token=status_token,
            portal_url=portal_url,
            scope="status",
        ))
    except Exception as exc:  # pragma: no cover
        print(f"[portal] status-link issuance failed: {exc}")

    # Step 2 (best-effort): spawn the Durable orchestration. If func host is
    # down, the candidate still has the status link and can refresh later.
    payload = {
        "workflow_id": workflow_id,
        "candidate_id": candidate_id,
        "role_id": role_id,
        "role_title": (workflow.metadata or {}).get("role_title") if workflow else None,
        "role_jurisdiction": (workflow.metadata or {}).get("role_jurisdiction") if workflow else None,
        "candidate": candidate,
    }
    try:
        resp = await schedule_new_orchestration(payload, function_name="HiringOrchestrator")
    except Exception as exc:  # pragma: no cover — surfaces in logs
        print(f"[portal] schedule_new_orchestration failed: {exc} (status link still issued; orchestration won't advance)")
        return
    instance_id = resp.get("id")
    if not instance_id:
        return

    # Record the instance_id on the candidate so /transcript and /offer can
    # raise external events on the right Durable instance.
    candidate["instance_id"] = instance_id
    app_state.store.upsert_candidate(candidate)

    # Auto-approve the budget HITL so the orchestration advances. The Finance
    # BP path is exercised separately (see /api/webhooks/finance-bp).
    try:
        await raise_orchestration_event(instance_id, "budget_approval", {
            "decision": "approve",
            "resolved_by": "portal_orchestration_auto",
        })
    except Exception as exc:  # pragma: no cover — surfaces in logs
        print(f"[portal] auto budget_approval failed: {exc}")


def make_offer_hitl_handler(app_state) -> Callable[[FleetEvent], None]:
    """Build a handler that issues an offer-scope magic-link token + email
    when the HiringOrchestrator suspends at Phase 9 (Offer).

    The internal_durable_event route emits `workflow.hitl.requested` with
    `reason="awaiting_offer_approval"` when Phase 9's suspended checkpoint
    fires. We react in this process — the orchestrator stays domain-pure
    and the candidate-side email side effect lives here.
    """

    def _handler(event: FleetEvent) -> None:
        if event.type != "workflow.hitl.requested":
            return
        extra = event.model_dump()
        if extra.get("reason") != "awaiting_offer_approval":
            return
        workflow_id = event.workflow_id
        if not workflow_id:
            return
        workflow = app_state.store.get_workflow(workflow_id)
        if workflow is None:
            return
        candidate_id = (workflow.metadata or {}).get("candidate_id")
        if not candidate_id:
            return
        candidate = app_state.store.get_candidate(candidate_id)
        if candidate is None:
            return

        token = app_state.magic_links.issue(
            candidate_id=candidate_id,
            scope="offer",
            ttl_seconds=_STATUS_LINK_TTL_SECONDS,
            single_use=True,
        )
        # Email URL points at /portal with the candidate's existing STATUS
        # token (not the offer token). /portal expects status-scope; it loads
        # the status payload and the candidate's active offer-scope token
        # gets attached as `offer_token`, which the OfferPanel uses for the
        # accept/decline POST. Linking to /portal with the offer token
        # directly would 404 — wrong scope on the status endpoint.
        active = app_state.magic_links.list_active()
        status_rows = [
            r for r in active
            if r.get("candidate_id") == candidate_id and r.get("scope") == "status"
        ]
        status_rows.sort(key=lambda r: r.get("issued_at") or 0, reverse=True)
        status_token = status_rows[0]["token"] if status_rows else token  # fallback unlikely
        portal_link_url = f"{_portal_base_url()}/portal?token={status_token}"
        safe_name = escape(candidate.get("name") or "there")
        safe_url = escape(portal_link_url, quote=True)
        html = (
            "<!doctype html><html><body style=\"font-family: system-ui, sans-serif;\">"
            f"<p>Hi {safe_name},</p>"
            "<p>We'd like to make you an offer. Review and accept or decline below — "
            "the link is single-use, valid for 7 days.</p>"
            f"<p><a href=\"{safe_url}\">Open your offer</a></p>"
            "<p>— Talent Acquisition</p>"
            "</body></html>"
        )
        try:
            app_state.email_sender.send(
                to=candidate.get("email") or "unknown@example.com",
                subject="Your offer is ready",
                html_body=html,
                candidate_id=candidate_id,
            )
        except EmailSendError as exc:  # pragma: no cover
            print(f"[portal] offer email send failed: {exc}")
        app_state.bus.emit(FleetEvent(
            type="magic_link.issued",
            workflow_id=workflow_id,
            candidate_id=candidate_id,
            magic_token=token,
            # `portal_url` is the working candidate-facing URL (status-scope
            # token); `magic_token` is the offer-scope token that the POST
            # /api/portal/offer/{token} endpoint consumes.
            portal_url=portal_link_url,
            scope="offer",
        ))

    return _handler


def make_candidate_applied_handler(app_state) -> Callable[[FleetEvent], None]:
    """Build a sync bus handler that schedules an async orchestration spawn
    when a candidate.applied event lands."""

    def _handler(event: FleetEvent) -> None:
        if event.type != "candidate.applied":
            return
        extra = event.model_dump()
        workflow_id = event.workflow_id
        candidate_id = extra.get("candidate_id")
        role_id = extra.get("role_id")
        if not (workflow_id and candidate_id and role_id):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No loop — emitter is on a sync thread. Skip; the orchestration
            # would not be reachable from here anyway.
            return
        loop.create_task(_spawn_hire_orchestration(
            app_state,
            candidate_id=candidate_id,
            workflow_id=workflow_id,
            role_id=role_id,
        ))

    return _handler


def attach(app_state) -> Callable[[], None]:
    """Subscribe all candidate-portal handlers to the bus. Returns a single
    unsubscribe callable so the lifespan teardown can detach all at once."""
    h_agent = make_handler(app_state)
    h_applied = make_candidate_applied_handler(app_state)
    h_offer = make_offer_hitl_handler(app_state)
    off_agent = app_state.bus.on("agent.completed", h_agent)
    off_applied = app_state.bus.on("candidate.applied", h_applied)
    off_offer = app_state.bus.on("workflow.hitl.requested", h_offer)

    def off() -> None:
        off_agent()
        off_applied()
        off_offer()

    return off
