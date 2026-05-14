"""agent_notification — composes the Adaptive Card + email body for a Red claim.

Called only on Red verdicts (Phase 5 enters only when route_by_verdict says
"notify"). The compose-and-send is split: this executor composes the payload,
and a downstream hook wires the actual Teams / Graph send. For the demo we
emit a `notification.sent` FleetEvent so the Control Plane shows the breach
notification in real time.
"""
from __future__ import annotations

from api.server.mcp_tools.claim_summary import claim_summary_tool
from api.server.mcp_tools.policy_cite import policy_cite_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "notification-composer"


def _emit_notification_event(claim_id: str, payload: dict) -> None:
    """Best-effort emit of a notification.sent FleetEvent. Wrapped in
    try/except so unit tests that don't bootstrap app_state don't fail."""
    try:
        from api.server.state import app_state
        from api.shared.events import FleetEvent
        app_state.bus.emit(FleetEvent(
            type="notification.sent",
            workflow_id=claim_id,
            claim_id=claim_id,
            subject=payload.get("subject"),
            tier=payload.get("tier"),
        ))
    except Exception:
        # Observability must never crash the caller.
        pass


async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]
    workflow_id = input.get("workflow_id")
    verdict = input.get("verdict")
    policy_clause = input.get("policy_clause") or input.get("classify", {}).get("policy_clause")
    escalation = input.get("escalation") or {}
    tier = escalation.get("tier") or "warning"

    # Phase 5 only runs on Red, but be defensive: skip cleanly otherwise.
    if verdict != "red":
        return {"notification": None, "skip_reason": f"verdict={verdict}"}

    prompt = (
        f"Compose a breach notification for expense claim `{claim_id}`. "
        f"Verdict: {verdict}. Policy clause: {policy_clause!r}. "
        f"Escalation tier: {tier}. Use `claim_summary` to load the claim "
        f"summary, then `policy_cite` to resolve the verbatim policy quote. "
        f"Return the JSON object specified in your skill — no prose."
    )

    notification = await run_agent_session(
        prompt=prompt,
        tools=[claim_summary_tool, policy_cite_tool],
        skill_dir=_SKILL_DIR,
        skill_label="notification-composer",
        workflow_id=workflow_id,
    )
    _emit_notification_event(claim_id, notification)
    return {"notification": notification}
