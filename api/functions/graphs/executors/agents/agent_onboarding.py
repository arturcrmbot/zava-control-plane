"""agent_onboarding — Phase 10 executor.

Calls the `avatar_render` MCP tool to generate a 30-second day-1 welcome
video, then writes the resulting Blob SAS URL onto the workflow's
`metadata.onboarding_video_url` so the candidate portal `/portal?token=…`
can play it back at the Onboarding phase. The portal's status route reads
the same key — see `api/server/routes/portal.py::status`.

Failure-mode: if avatar_render returns `result_type=failure` (Azure Speech
unconfigured, render error, or transport=mock), we log a warning and skip
persisting — the portal then renders the no-video Onboarding panel.

Prerecord short-circuit
-----------------------
For demo stability we look up the active Agency data namespace's
`welcome-videos/<slug>.mp4`
keyed on a slugified candidate name BEFORE calling Azure Speech. Hits
return immediately (no network, no minute-long render, no Azurite
dependency). After a successful Azure render the resulting bytes are
also persisted to the same path so subsequent demos hit the local cache.
The file is served by FastAPI at `/api/portal/welcome-video/<slug>.mp4`
(see api/server/routes/portal.py).
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from api.functions.webhook import emit_sync as _webhook_emit_sync
from api.server.mcp_tools.avatar_render import avatar_render

log = logging.getLogger(__name__)


# Resolve the prerecord directory relative to the repo root.
def _prerecord_dir() -> Path:
    from api.shared.vertical_loader import active_runtime

    return active_runtime().data_dir / "welcome-videos"


def _candidate_slug(candidate_name: str) -> str:
    """Slugify a candidate name for use as a stable filename + URL path.

    'Alex Doe' -> 'alex-doe', 'Jane O\\'Brien' -> 'jane-o-brien'.
    """
    s = candidate_name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "candidate"


def _portal_base_url() -> str:
    """The base URL the candidate portal hits us on. Defaults to the local
    FastAPI bind. Set via PORTAL_API_BASE_URL when fronted by a tunnel."""
    return os.environ.get("PORTAL_API_BASE_URL", "http://localhost:3101").rstrip("/")


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
        f"Welcome to Zava, {candidate_name}. We're delighted you've accepted "
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

    out: dict = {
        "phase": "Onboarding",
        "workflow_id": workflow_id,
        "candidate_name": candidate_name,
        "role_title": role_title,
        "avatar_character": avatar_character,
        "avatar_style": avatar_style,
    }

    # ----- Prerecord short-circuit (P0 demo path) -----
    # If a candidate-named MP4 has been pre-staged on disk, serve it
    # directly — instant, no Azure call, survives Azurite wipes. Stable
    # candidates like 'Alex Doe' (the canonical demo applicant) get
    # rendered once then committed to the active pack's welcome-video cache.
    slug = _candidate_slug(candidate_name)
    prerecord_path = _prerecord_dir() / f"{slug}.mp4"
    if prerecord_path.is_file():
        video_url = f"{_portal_base_url()}/api/portal/welcome-video/{slug}.mp4"
        log.info(
            "agent_onboarding: prerecord hit for %s -> %s (%d bytes on disk)",
            slug, video_url, prerecord_path.stat().st_size,
        )
        out["onboarding_video_url"] = video_url
        out["avatar_cached"] = True
        out["avatar_source"] = "prerecord"
        _persist_video_url(workflow_id, video_url)
        return out

    # ----- Cold path: real Azure Speech batch synthesis -----
    result = avatar_render(
        script=script,
        avatar_character=avatar_character,
        avatar_style=avatar_style,
    )

    if result.result_type == "success" and result.video_url:
        out["onboarding_video_url"] = result.video_url
        out["avatar_cached"] = result.cached
        out["avatar_source"] = "azure-speech"
        _persist_video_url(workflow_id, result.video_url)
        # Snapshot to disk so future demos for this candidate are instant
        # and immune to Azurite resets. Best-effort — failure here is OK.
        try:
            _snapshot_to_prerecord(result.video_url, prerecord_path)
        except Exception as exc:  # pragma: no cover — best effort
            log.warning("snapshot to %s failed: %s", prerecord_path, exc)
    else:
        log.warning(
            "avatar render skipped/failed for workflow=%s: %s",
            workflow_id,
            result.error,
        )
        out["avatar_error"] = result.error

    return out


def _persist_video_url(workflow_id: str | None, video_url: str) -> None:
    """Persist the video URL to workflow.metadata.onboarding_video_url.

    The activity runs in the func worker process; FastAPI maintains its
    own app_state.store. Writing locally only updates the worker's copy
    and the candidate-portal /status route would never see the URL.
    Send via the webhook bridge so FastAPI's app_state gets updated.

    Falls back to a direct store write so that unit tests without a live
    FastAPI continue to pass.
    """
    if not workflow_id:
        return
    # Webhook path (production): tells FastAPI's bridge to update metadata.
    # Uses the sync httpx client — asyncio.run() fails here because the
    # Functions host activity runner already has a running event loop.
    try:
        _webhook_emit_sync(
            workflow_id, workflow_id, "onboarding_video_ready",
            {"video_url": video_url},
        )
    except Exception as exc:  # pragma: no cover — best-effort
        log.warning("webhook emit onboarding_video_ready failed: %s", exc)
    # Local fallback (tests / spine-only paths): write to whichever app_state
    # the current process has. Harmless when FastAPI's process already wrote
    # via the webhook above.
    try:
        from api.server.state import app_state

        wf = app_state.store.get_workflow(workflow_id)
        if wf is None:
            return
        wf.metadata = dict(wf.metadata or {})
        wf.metadata["onboarding_video_url"] = video_url
        app_state.store.upsert_workflow(wf)
    except Exception as exc:  # pragma: no cover — best-effort
        log.warning("persist video_url local fallback failed: %s", exc)


def _snapshot_to_prerecord(blob_sas_url: str, dest: Path) -> None:
    """Download a freshly-rendered MP4 from its Azure Blob SAS URL and save
    it under the active pack's welcome-video cache.

    Subsequent runs for the same candidate hit the prerecord short-circuit
    and skip Azure entirely — instant playback, immune to Azurite resets.
    """
    import httpx

    if dest.exists():
        return  # already snapshotted
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30.0) as c:
        r = c.get(blob_sas_url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    log.info("snapshotted welcome video to %s (%d bytes)", dest, dest.stat().st_size)
