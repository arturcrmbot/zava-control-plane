"""Candidate-portal route tests — covers /apply, /status, /offer, /admin/links.

Each test rebuilds an isolated AppState (sqlite for magic-link store, on-disk
outbox dir for emails) inside `tmp_path`. The blob_store and durable_client
are stubbed so the suite runs without Azurite or the Functions host.
"""
from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient

from api.shared.types import Workflow


class _StubBlobStore:
    """Minimal in-memory BlobStore replacement so /apply works without Azurite."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def put(self, name: str, data: bytes, *, content_type: str) -> str:
        self.blobs[name] = data
        return f"https://stub.blob/portal-cvs/{name}"

    def sas_url(self, name: str, *, ttl_seconds: int) -> str:
        return f"https://stub.blob/portal-cvs/{name}?se=stub&sig=stub"

    def exists(self, name: str) -> bool:
        return name in self.blobs


def _make_workflow(workflow_id: str, role_id: str) -> Workflow:
    now = time.time()
    return Workflow(
        id=workflow_id,
        type="hiring",
        current_phase="Triage",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-HR",
        orchestration_instance_id=f"INST-{workflow_id}",
        metadata={"role_id": role_id},
    )


@pytest.fixture
def portal_client(tmp_path, monkeypatch):
    """Build a fresh AppState bound to tmp_path so each test starts clean.

    Yields (TestClient, AppState) so the test can poke the singletons (issue
    a magic-link, seed a workflow, etc.) before driving the route.
    """
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    # Set to empty rather than delete: the api.server.state module calls
    # load_dotenv() at import time which would re-populate these from .env
    # (pointing at Azurite, which isn't running in tests). load_dotenv does
    # NOT override an existing env var — even an empty one — so this keeps
    # _build_blob_store()'s `if not conn` check happy.
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "")
    monkeypatch.setenv("ACS_EMAIL_CONNECTION_STRING", "")
    monkeypatch.setenv("PORTAL_BASE_URL", "http://localhost:5174")

    # Drop cached modules so AppState() picks up the new env.
    import sys
    for mod in [
        "api.server.state",
        "api.server.main",
        "api.server.routes.portal",
    ]:
        sys.modules.pop(mod, None)

    from api.server.state import app_state
    # Stub blob_store so /apply doesn't hit Azurite.
    app_state.blob_store = _StubBlobStore()

    # Seed one HiringOrchestrator workflow per known demo req.
    app_state.store.upsert_workflow(_make_workflow("HIRE-A", "REQ-SDE-USA-DEMO"))
    app_state.store.upsert_workflow(_make_workflow("HIRE-B", "REQ-SDE-DE-DEMO"))
    app_state.store.upsert_workflow(_make_workflow("HIRE-C", "REQ-CD-USA-DEMO"))

    from api.server.main import app
    client = TestClient(app)
    yield client, app_state


# ---------------------------------------------------------------- Task 5: /apply


def test_apply_creates_candidate_and_attaches_to_workflow(portal_client):
    client, app_state = portal_client
    pdf_bytes = b"%PDF-1.4 fake"
    resp = client.post(
        "/api/portal/apply",
        data={
            "role_id": "REQ-SDE-USA-DEMO",
            "name": "Alice Engineer",
            "email": "alice@example.com",
        },
        files={"cv": ("alice.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "submitted"
    assert body["candidate_id"].startswith("C-")
    assert body["workflow_id"] == "HIRE-A"
    # Candidate persisted on the store and bound to the workflow.
    cand = app_state.store.get_candidate(body["candidate_id"])
    assert cand is not None
    assert cand["name"] == "Alice Engineer"
    assert cand["workflow_id"] == "HIRE-A"
    # Workflow metadata reflects the new candidate.
    w = app_state.store.get_workflow("HIRE-A")
    assert w.metadata["candidate_id"] == body["candidate_id"]


def test_apply_rejects_unknown_role(portal_client):
    client, _ = portal_client
    resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-DOES-NOT-EXIST", "name": "X", "email": "x@y.z"},
        files={"cv": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert resp.status_code == 404


def test_apply_rejects_non_pdf_cv(portal_client):
    client, _ = portal_client
    resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-SDE-USA-DEMO", "name": "X", "email": "x@y.z"},
        files={"cv": ("x.txt", io.BytesIO(b"hi"), "text/plain")},
    )
    assert resp.status_code == 415


# ---------------------------------------------------------------- Task 6: /status


def test_status_returns_candidate_phase_for_valid_token(portal_client):
    client, app_state = portal_client
    # Apply first so we have a candidate bound to a workflow.
    apply_resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-SDE-USA-DEMO", "name": "Bob", "email": "b@x.y"},
        files={"cv": ("b.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    cid = apply_resp.json()["candidate_id"]
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="status", ttl_seconds=3600, single_use=False,
    )

    resp = client.get(f"/api/portal/status/{token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidate"]["id"] == cid
    assert body["phase"] == "Triage"


def test_status_404_on_invalid_token(portal_client):
    client, _ = portal_client
    resp = client.get("/api/portal/status/totally-bogus-token")
    assert resp.status_code == 404


def test_status_410_on_expired_token(portal_client):
    client, app_state = portal_client
    apply_resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-SDE-USA-DEMO", "name": "Eve", "email": "e@x.y"},
        files={"cv": ("e.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    cid = apply_resp.json()["candidate_id"]
    # ttl_seconds=0 -> immediately expired (peek compares strict >).
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="status", ttl_seconds=0, single_use=False,
    )
    time.sleep(0.05)
    resp = client.get(f"/api/portal/status/{token}")
    assert resp.status_code == 410


def test_status_repeatable_does_not_consume(portal_client):
    """status-scope tokens are repeatable — refreshing the page should not
    invalidate the link."""
    client, app_state = portal_client
    apply_resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-SDE-USA-DEMO", "name": "Repeat", "email": "r@x.y"},
        files={"cv": ("r.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    cid = apply_resp.json()["candidate_id"]
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="status", ttl_seconds=3600, single_use=False,
    )
    for _ in range(3):
        resp = client.get(f"/api/portal/status/{token}")
        assert resp.status_code == 200


# ---------------------------------------------------------------- Task 7: /offer


def test_offer_accept_consumes_token_and_emits_event(portal_client, monkeypatch):
    client, app_state = portal_client
    apply_resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-SDE-USA-DEMO", "name": "Cara", "email": "c@x.y"},
        files={"cv": ("c.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    cid = apply_resp.json()["candidate_id"]
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="offer", ttl_seconds=3600, single_use=True,
    )

    # Stub raise_orchestration_event so we don't hit the Functions host.
    raised: list = []

    async def _fake_raise(instance_id, event_name, event_data):
        raised.append((instance_id, event_name, event_data))

    import api.server.routes.portal as portal_module
    monkeypatch.setattr(portal_module, "raise_orchestration_event", _fake_raise)

    events: list = []
    app_state.bus.on("offer.decided", lambda e: events.append(e))

    resp = client.post(
        f"/api/portal/offer/{token}", params={"decision": "accept"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["decision"] == "accept"
    assert raised and raised[0][1] == "offer_approval"
    assert events and events[0].type == "offer.decided"


def test_offer_decline_works(portal_client, monkeypatch):
    client, app_state = portal_client
    apply_resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-CD-USA-DEMO", "name": "Dan", "email": "d@x.y"},
        files={"cv": ("d.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    cid = apply_resp.json()["candidate_id"]
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="offer", ttl_seconds=3600, single_use=True,
    )

    async def _noop(*a, **k):
        pass

    import api.server.routes.portal as portal_module
    monkeypatch.setattr(portal_module, "raise_orchestration_event", _noop)

    resp = client.post(
        f"/api/portal/offer/{token}", params={"decision": "decline"},
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "decline"


def test_offer_double_consume_is_rejected(portal_client, monkeypatch):
    client, app_state = portal_client
    apply_resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-SDE-DE-DEMO", "name": "F", "email": "f@x.y"},
        files={"cv": ("f.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    cid = apply_resp.json()["candidate_id"]
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="offer", ttl_seconds=3600, single_use=True,
    )

    async def _noop(*a, **k):
        pass

    import api.server.routes.portal as portal_module
    monkeypatch.setattr(portal_module, "raise_orchestration_event", _noop)

    first = client.post(f"/api/portal/offer/{token}", params={"decision": "accept"})
    assert first.status_code == 200
    second = client.post(f"/api/portal/offer/{token}", params={"decision": "accept"})
    assert second.status_code == 409


def test_offer_invalid_decision_400(portal_client):
    client, app_state = portal_client
    apply_resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-SDE-USA-DEMO", "name": "G", "email": "g@x.y"},
        files={"cv": ("g.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    cid = apply_resp.json()["candidate_id"]
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="offer", ttl_seconds=3600, single_use=True,
    )
    resp = client.post(f"/api/portal/offer/{token}", params={"decision": "maybe"})
    assert resp.status_code == 400


# ----------------------------------------------------- Task 13: admin/links


def test_admin_links_lists_active_with_candidate_join(portal_client):
    client, app_state = portal_client
    apply_resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-SDE-USA-DEMO", "name": "Heidi", "email": "h@x.y"},
        files={"cv": ("h.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    cid = apply_resp.json()["candidate_id"]
    app_state.magic_links.issue(
        candidate_id=cid, scope="status", ttl_seconds=3600, single_use=False,
    )

    resp = client.get("/api/portal/admin/links")
    assert resp.status_code == 200
    body = resp.json()
    assert "links" in body
    rows = body["links"]
    assert any(r["candidate_id"] == cid and r.get("name") == "Heidi" for r in rows)
