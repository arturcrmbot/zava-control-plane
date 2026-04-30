"""Tests for the two new Phase 6 activities — `issue_screen_link_activity`
and `send_screen_email_activity`. They are the I/O boundary between the
HiringOrchestrator and the candidate-portal magic-link store / ACS Email
sender; the orchestration generator stays pure.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest


@pytest.fixture
def fresh_state(tmp_path, monkeypatch):
    """Build a fresh AppState bound to tmp_path so the activities have
    a sqlite magic-link store and an outbox-only EmailSender to write into.
    """
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("ACS_EMAIL_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("PORTAL_BASE_URL", "http://localhost:5174")

    for mod in [
        "api.server.state",
        "api.functions.workflows.voice_screen_activities",
    ]:
        sys.modules.pop(mod, None)

    from api.server.state import app_state
    yield app_state


def _seed_candidate(app_state, candidate_id="C-XYZ1", name="Vera",
                    email="vera@example.com"):
    app_state.store._candidates[candidate_id] = {
        "id": candidate_id,
        "name": name,
        "email": email,
        "workflow_id": "HIRE-A",
        "instance_id": "INST-HIRE-A",
    }


def test_issue_screen_link_mints_screen_scope_token(fresh_state):
    app_state = fresh_state
    _seed_candidate(app_state)
    from api.functions.workflows.voice_screen_activities import issue_screen_link_activity

    result = issue_screen_link_activity({"candidate_id": "C-XYZ1"})

    assert "token" in result
    assert result["candidate_id"] == "C-XYZ1"
    assert result["portal_url"].endswith(f"/screen?token={result['token']}")
    # Token resolves under scope=screen and binds to the candidate.
    peek = app_state.magic_links.peek(result["token"], scope="screen")
    assert peek is not None
    assert peek["candidate_id"] == "C-XYZ1"


def test_issue_screen_link_uses_default_24h_ttl_when_unspecified(fresh_state):
    app_state = fresh_state
    _seed_candidate(app_state, candidate_id="C-TTL")
    from api.functions.workflows.voice_screen_activities import issue_screen_link_activity

    result = issue_screen_link_activity({"candidate_id": "C-TTL"})
    peek = app_state.magic_links.peek(result["token"], scope="screen")
    # 24h = 86400s; allow a small clock-drift margin.
    ttl = peek["expires_at"] - peek["issued_at"]
    assert 86300 < ttl <= 86400


def test_send_screen_email_writes_to_outbox(fresh_state):
    app_state = fresh_state
    _seed_candidate(app_state, candidate_id="C-EMAIL", name="Eve",
                    email="eve@example.com")
    from api.functions.workflows.voice_screen_activities import (
        issue_screen_link_activity,
        send_screen_email_activity,
    )
    link = issue_screen_link_activity({"candidate_id": "C-EMAIL"})

    result = send_screen_email_activity({
        "candidate_id": "C-EMAIL",
        "token": link["token"],
        "portal_url": link["portal_url"],
    })

    assert result["sent"] is True
    assert result["message_id"]
    # Outbox-only EmailSender always persists the HTML body.
    outbox = Path(app_state.email_sender.outbox_dir)
    assert outbox.exists()
    files = list(outbox.glob("*.html"))
    assert len(files) >= 1
    body = files[0].read_text(encoding="utf-8")
    assert "Eve" in body
    assert link["token"] in body


def test_send_screen_email_unknown_candidate_returns_not_sent(fresh_state):
    """Activity is best-effort: if the candidate vanished before the email
    fires (rare but possible — store is in-memory), we return a clear
    `sent: False, reason: unknown_candidate` rather than crashing the
    orchestration."""
    from api.functions.workflows.voice_screen_activities import send_screen_email_activity

    result = send_screen_email_activity({
        "candidate_id": "C-DOESNTEXIST",
        "token": "tok-1",
        "portal_url": "http://localhost:5174/screen?token=tok-1",
    })
    assert result["sent"] is False
    assert result["reason"] == "unknown_candidate"
