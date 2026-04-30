"""agent_onboarding — Phase 10 executor.

Calls the `avatar_render` MCP tool to generate a 30-second day-1 welcome
video, then writes the resulting Blob SAS URL onto the workflow's
`metadata.onboarding_video_url` so the candidate portal `/portal?token=…`
can play it back at the Onboarding phase. The portal's status route reads
the same key — see `api/server/routes/portal.py::status`.

Failure-mode: if avatar_render returns `result_type=failure` (Azure Speech
unconfigured, render error, or transport=mock), we log a warning and skip
persisting — the portal then renders the no-video Onboarding panel.
"""
from __future__ import annotations

import logging

from api.server.mcp_tools.avatar_render import avatar_render

log = logging.getLogger(__name__)


def _welcome_script(
    *,
    candidate_name: str,
    role_title: str,
    manager_name: str | None = None,
) -> str:
    mgr = (
        f" Your manager, {manager_name}, will meet you on day one."
        if manager_name
        else ""
    )
    return (
        f"Welcome to WPP, {candidate_name}. We're delighted you've accepted "
        f"the offer for {role_title}. On day one we'll walk you through your "
        f"laptop setup, your accounts, and your first-week onboarding plan."
        f"{mgr} See you soon."
    )


def _avatar_for_role(role_title: str | None) -> tuple[str, str]:
    """Pick a (character, style) pair compatible with Azure Speech's prebuilt
    avatar matrix. Each character only supports specific styles — passing
    an unsupported pair returns 400 from the batch synthesis endpoint.

    Reference: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/text-to-speech-avatar/avatar-gestures-with-ssml
    """
    if not role_title:
        return ("lisa", "graceful-sitting")
    rt = role_title.lower()
    if any(k in rt for k in ("data", "engineer", "analyst")):
        # harry only supports "business"
        return ("harry", "business")
    if "creative" in rt or "design" in rt:
        # lori supports graceful / formal / casual
        return ("lori", "graceful")
    return ("lisa", "graceful-sitting")


async def execute(input: dict) -> dict:
    """Render the welcome video; persist the URL onto workflow metadata."""
    workflow_id = input.get("workflow_id") or input.get("instance_id")
    candidate_name = (
        input.get("candidate_name")
        or (input.get("candidate") or {}).get("name")
        or "there"
    )
    role_title = (
        input.get("role_title")
        or (input.get("role") or {}).get("title")
        or "your new role"
    )
    manager_name = (
        input.get("manager_name")
        or (input.get("manager") or {}).get("name")
    )

    script = _welcome_script(
        candidate_name=candidate_name,
        role_title=role_title,
        manager_name=manager_name,
    )
    avatar_character, avatar_style = _avatar_for_role(role_title)

    result = avatar_render(
        script=script,
        avatar_character=avatar_character,
        avatar_style=avatar_style,
    )

    out: dict = {
        "phase": "Onboarding",
        "workflow_id": workflow_id,
        "candidate_name": candidate_name,
        "role_title": role_title,
        "avatar_character": avatar_character,
        "avatar_style": avatar_style,
    }

    if result.result_type == "success" and result.video_url:
        out["onboarding_video_url"] = result.video_url
        out["avatar_cached"] = result.cached
        _persist_video_url(workflow_id, result.video_url)
    else:
        log.warning(
            "avatar render skipped/failed for workflow=%s: %s",
            workflow_id,
            result.error,
        )
        out["avatar_error"] = result.error

    return out


def _persist_video_url(workflow_id: str | None, video_url: str) -> None:
    """Best-effort: write the URL to workflow.metadata.onboarding_video_url
    via app_state.store. Wrapped in try/except so unit tests that don't
    bootstrap app_state still work."""
    if not workflow_id:
        return
    try:
        from api.server.state import app_state

        wf = app_state.store.get_workflow(workflow_id)
        if wf is None:
            return
        wf.metadata = dict(wf.metadata or {})
        wf.metadata["onboarding_video_url"] = video_url
        app_state.store.upsert_workflow(wf)
    except Exception as exc:  # pragma: no cover — best-effort
        log.warning("persist video_url failed: %s", exc)
