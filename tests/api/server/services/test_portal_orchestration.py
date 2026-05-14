"""Portal orchestration: cv_crystalliser → magic-link issuance + email send.

Builds a minimal AppState (real MagicLinkStore on tmp_path sqlite, real
EmailSender in fallback mode writing to a tmp outbox dir, in-memory
StateStore) and emits a synthetic agent.completed event. Asserts the
bridge issues a status-scope token and writes the email HTML to the outbox.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from api.server.services.email_send import EmailSender
from api.server.services.event_bus import EventBus
from api.server.services.magic_link import MagicLinkStore
from api.server.services.portal_orchestration import attach
from api.server.services.state_store import StateStore
from api.shared.events import FleetEvent
from api.shared.types import Workflow


class _FakeAppState:
    """Hand-rolled AppState double — only the fields portal_orchestration touches."""

    def __init__(self, *, tmp_path: Path) -> None:
        self.bus = EventBus()
        self.store = StateStore()
        self.magic_links = MagicLinkStore(db_path=tmp_path / "ml.sqlite")
        self.email_sender = EmailSender(
            connection_string=None,
            sender_address=None,
            outbox_dir=tmp_path / "outbox",
        )


def _seed_workflow_and_candidate(
    state: _FakeAppState,
    *,
    workflow_id: str = "HIRE-T",
    role_id: str = "REQ-SDE-USA-DEMO",
    candidate_id: str = "C-DEADBEEF",
    name: str = "Test Person",
    email: str = "test@example.com",
) -> None:
    now = time.time()
    state.store.upsert_workflow(Workflow(
        id=workflow_id,
        type="hiring",
        current_phase="Triage",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-HR",
        orchestration_instance_id=f"INST-{workflow_id}",
        metadata={"role_id": role_id},
    ))
    state.store.attach_candidate_to_role(role_id, {
        "id": candidate_id,
        "name": name,
        "email": email,
        "cv_url": "https://stub/cv.pdf",
        "role_id": role_id,
    })


def test_emits_magic_link_and_email_when_cv_crystalliser_completes(tmp_path):
    state = _FakeAppState(tmp_path=tmp_path)
    _seed_workflow_and_candidate(state)
    off = attach(state)

    issued: list[FleetEvent] = []
    state.bus.on("magic_link.issued", lambda e: issued.append(e))

    state.bus.emit(FleetEvent(
        type="agent.completed",
        workflow_id="HIRE-T",
        agent_label="cv_crystalliser",
        agent_run_id="ar-test",
        extracted_json={"shortlist_score": 0.9},
    ))

    # A status-scope token is now active for our candidate.
    active = state.magic_links.list_active()
    assert len(active) == 1
    assert active[0]["candidate_id"] == "C-DEADBEEF"
    assert active[0]["scope"] == "status"

    # Outbox has exactly one email file containing the portal URL.
    outbox = list((tmp_path / "outbox").glob("*.html"))
    assert len(outbox) == 1
    body = outbox[0].read_text(encoding="utf-8")
    assert active[0]["token"] in body
    assert "Test Person" in body

    # magic_link.issued bus event was emitted.
    assert issued and issued[0].type == "magic_link.issued"
    off()


def test_skips_when_score_below_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTLIST_THRESHOLD", "0.7")
    # Re-import so the threshold env var is picked up freshly.
    import importlib
    import api.server.services.portal_orchestration as po
    importlib.reload(po)

    state = _FakeAppState(tmp_path=tmp_path)
    _seed_workflow_and_candidate(state)
    off = po.attach(state)

    state.bus.emit(FleetEvent(
        type="agent.completed",
        workflow_id="HIRE-T",
        agent_label="cv_crystalliser",
        extracted_json={"shortlist_score": 0.4},
    ))

    assert state.magic_links.list_active() == []
    assert list((tmp_path / "outbox").glob("*.html")) == []
    off()


def test_ignores_other_agent_labels(tmp_path):
    state = _FakeAppState(tmp_path=tmp_path)
    _seed_workflow_and_candidate(state)
    off = attach(state)

    state.bus.emit(FleetEvent(
        type="agent.completed",
        workflow_id="HIRE-T",
        agent_label="receipt_validator",
        extracted_json={"shortlist_score": 0.99},
    ))
    assert state.magic_links.list_active() == []
    off()


def test_ignores_completion_for_unknown_candidate(tmp_path):
    state = _FakeAppState(tmp_path=tmp_path)
    # Workflow exists but no candidate has been attached yet (apply hasn't
    # happened); the bridge should silently no-op.
    now = time.time()
    state.store.upsert_workflow(Workflow(
        id="HIRE-X",
        type="hiring",
        current_phase="Triage",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-HR",
        metadata={"role_id": "REQ-X"},
    ))
    off = attach(state)

    state.bus.emit(FleetEvent(
        type="agent.completed",
        workflow_id="HIRE-X",
        agent_label="cv_crystalliser",
    ))
    assert state.magic_links.list_active() == []
    off()
