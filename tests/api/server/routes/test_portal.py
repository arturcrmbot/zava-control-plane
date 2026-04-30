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
        jurisdiction="London-WPP",
        agency="WPP-HR",
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
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("ACS_EMAIL_CONNECTION_STRING", raising=False)
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
