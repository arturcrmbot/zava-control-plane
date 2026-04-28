"""agent_audit_summariser — Phase 7 executor.

Composes a one-paragraph narrative compliance summary for a completed
expense workflow. Skills-first: the prompt names the workflow_id; the
model invokes `claim_summary` + `audit_query` itself per the
audit-summariser skill's `allowed-tools` frontmatter.

Emits `audit.summary.composed` so the Fleet Manager rail can render the
summary in real time.
"""
from __future__ import annotations

from api.server.mcp_tools.audit_query import audit_query_tool
from api.server.mcp_tools.claim_summary import claim_summary_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "audit-summariser"


def _emit_audit_event(workflow_id: str, payload: dict) -> None:
    """Best-effort emit of audit.summary.composed for SSE consumers.
    Wrapped in try/except so unit tests that don't bootstrap app_state
    don't fail."""
    try:
        from api.server.state import app_state
        from api.shared.events import FleetEvent
        app_state.bus.emit(FleetEvent(
            type="audit.summary.composed",
            workflow_id=workflow_id,
            claim_id=payload.get("claim_id"),
            summary_chars=len((payload.get("summary") or "")),
        ))
    except Exception:
        pass


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id") or input.get("instance_id")
    claim = input.get("claim") or {}
    claim_id = claim.get("claim_id") or input.get("claim_id")

    prompt = (
        f"Compose a 1-paragraph audit summary for completed workflow "
        f"`{workflow_id}` (claim `{claim_id}`).\n\n"
        f"Use `claim_summary` to load the claim line, then `audit_query` "
        f"with `workflow_id={workflow_id!r}` and `limit=50` to load the "
        f"full ledger. Quote at least one specific (timestamp, actor_id, "
        f"action) triple. Return the JSON object specified in your skill "
        f"— no prose, no markdown."
    )

    summary = await run_agent_session(
        prompt=prompt,
        tools=[claim_summary_tool, audit_query_tool],
        skill_dir=_SKILL_DIR,
        skill_label="audit-summariser",
    )
    _emit_audit_event(workflow_id or "?", summary if isinstance(summary, dict) else {})
    return {"audit": summary}
