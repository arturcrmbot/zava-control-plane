"""Voice-screen portal route tests — /api/portal/voice/screen-resolve + /transcript.

Mirrors `tests/api/server/routes/test_portal.py` fixture pattern: rebuild
AppState bound to tmp_path, stub blob_store, seed one HiringOrchestrator
workflow per known demo req.

The tests focus on the two route contracts owned by this stream:

  GET  /api/portal/voice/screen-resolve?token=...
       Peeks a `screen`-scope token and returns the candidate id without
       consuming. 404 on unknown token, 410 on expired.

  POST /api/portal/voice/{candidate_id}/transcript
       Validates the screen token, persists the transcript on the candidate
       record, raises the `voice_complete` external event so Phase 6 of the
       Durable orchestration resumes. 403 on invalid/mismatched token, 404
       on unknown candidate.
"""
from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient

from api.shared.types import Workflow


class _StubBlobStore:
    """In-memory BlobStore replacement so /apply works without Azurite."""

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
        current_phase="Voice",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-HR",
        orchestration_instance_id=f"INST-{workflow_id}",
        metadata={"role_id": role_id},
    )


@pytest.fixture
def voice_client(tmp_path, monkeypatch):
    """Fresh AppState bound to tmp_path — yields (TestClient, app_state).

    We mount only the two routers we need (portal + portal_voice) on a fresh
    FastAPI app so the test doesn't drag in api.server.main and its
    Fleet-Manager dependency on an unrelated copilot SDK import that is
    pre-broken on main. This mirrors the pattern used by other route tests
    that side-step the full-app wire-up.
    """
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    # setenv('') not delenv: load_dotenv() at api.server.state import time
    # would otherwise re-populate these from .env (Azurite, not running).
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "")
    monkeypatch.setenv("ACS_EMAIL_CONNECTION_STRING", "")
    monkeypatch.setenv("PORTAL_BASE_URL", "http://localhost:5174")

    import sys
    for mod in [
        "api.server.state",
        "api.server.routes.portal",
        "api.server.routes.portal_voice",
    ]:
        sys.modules.pop(mod, None)

    from api.server.state import app_state
    app_state.blob_store = _StubBlobStore()

    app_state.store.upsert_workflow(_make_workflow("HIRE-A", "REQ-SDE-USA-DEMO"))

    from fastapi import FastAPI
    from api.server.routes.portal import router as portal_router
    from api.server.routes.portal_voice import router as portal_voice_router
    app = FastAPI()
    app.include_router(portal_router)
    app.include_router(portal_voice_router)
    client = TestClient(app)
    yield client, app_state


def _seed_candidate(client, app_state, role_id="REQ-SDE-USA-DEMO"):
    """Apply through the public route so candidate is bound to a workflow."""
    resp = client.post(
        "/api/portal/apply",
        data={"role_id": role_id, "name": "Vera Voice", "email": "v@x.y"},
        files={"cv": ("v.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["candidate_id"]


# ---------------------------------------------------------------- screen-resolve


def test_screen_resolve_returns_candidate_id_for_valid_token(voice_client):
    client, app_state = voice_client
    cid = _seed_candidate(client, app_state)
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="screen", ttl_seconds=3600, single_use=True,
    )
    resp = client.get(f"/api/portal/voice/screen-resolve?token={token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidate_id"] == cid


def test_screen_resolve_404_on_unknown_token(voice_client):
    client, _ = voice_client
    resp = client.get("/api/portal/voice/screen-resolve?token=bogus")
    assert resp.status_code == 404


def test_screen_resolve_410_on_expired_token(voice_client):
    client, app_state = voice_client
    cid = _seed_candidate(client, app_state)
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="screen", ttl_seconds=0, single_use=True,
    )
    time.sleep(0.05)
    resp = client.get(f"/api/portal/voice/screen-resolve?token={token}")
    assert resp.status_code == 410


def test_screen_resolve_does_not_consume_token(voice_client):
    """peek must not mark the token as consumed — the candidate is about to
    actually start the call which will redeem the token in /transcript."""
    client, app_state = voice_client
    cid = _seed_candidate(client, app_state)
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="screen", ttl_seconds=3600, single_use=True,
    )
    client.get(f"/api/portal/voice/screen-resolve?token={token}").raise_for_status()
    # Second peek should still succeed.
    resp2 = client.get(f"/api/portal/voice/screen-resolve?token={token}")
    assert resp2.status_code == 200


# ---------------------------------------------------------------- /transcript


def test_transcript_callback_raises_voice_complete(voice_client, monkeypatch):
    client, app_state = voice_client
    cid = _seed_candidate(client, app_state)
    token = app_state.magic_links.issue(
        candidate_id=cid, scope="screen", ttl_seconds=3600, single_use=True,
    )

    raised: list[tuple[str, str, dict]] = []

    async def fake_raise(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))

    monkeypatch.setattr(
        "api.server.routes.portal_voice.raise_orchestration_event", fake_raise,
    )

    resp = client.post(
        f"/api/portal/voice/{cid}/transcript",
        json={
            "token": token,
            "transcript": [
                {"role": "agent", "text": "Hello", "ts": 0.0},
                {"role": "candidate", "text": "Hi", "ts": 1.5},
            ],
            "score": 7.8,
            "duration_s": 124.5,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    # Durable event raised on the right instance with the right name + payload.
    assert len(raised) == 1
    assert raised[0][0] == "INST-HIRE-A"
    assert raised[0][1] == "voice_complete"
    assert raised[0][2]["score"] == 7.8
    assert raised[0][2]["candidate_id"] == cid

    # Transcript persisted on the candidate record.
    cand = app_state.store.get_candidate(cid)
    assert "voice_transcript" in cand
    # Each turn appended individually so the /status replay can iterate.
    assert len(cand["voice_transcript"]) == 2
    assert cand["voice_transcript"][0]["text"] == "Hello"


def test_transcript_callback_403_on_invalid_token(voice_client):
    client, app_state = voice_client
    cid = _seed_candidate(client, app_state)
    resp = client.post(
        f"/api/portal/voice/{cid}/transcript",
        json={
            "token": "totally-bogus",
            "transcript": [],
            "score": 5.0,
            "duration_s": 30.0,
        },
    )
    assert resp.status_code == 403


def test_transcript_callback_403_on_token_candidate_mismatch(voice_client):
    """Token issued for candidate A must not work for candidate B."""
    client, app_state = voice_client
    cid_a = _seed_candidate(client, app_state)
    # Manually register a second candidate dict so we have a B to mismatch against.
    cid_b = "C-BBBBBBBB"
    app_state.store._candidates[cid_b] = {
        "id": cid_b,
        "workflow_id": "HIRE-A",
        "instance_id": "INST-HIRE-A",
        "name": "Other",
    }
    token = app_state.magic_links.issue(
        candidate_id=cid_a, scope="screen", ttl_seconds=3600, single_use=True,
    )
    resp = client.post(
        f"/api/portal/voice/{cid_b}/transcript",
        json={
            "token": token, "transcript": [], "score": 5.0, "duration_s": 30.0,
        },
    )
    assert resp.status_code == 403


def test_transcript_callback_404_on_unknown_candidate(voice_client, monkeypatch):
    client, app_state = voice_client
    # Issue a screen token for a candidate id that has no record on the store.
    bogus_cid = "C-DEADBEEF"
    token = app_state.magic_links.issue(
        candidate_id=bogus_cid, scope="screen", ttl_seconds=3600, single_use=True,
    )
    resp = client.post(
        f"/api/portal/voice/{bogus_cid}/transcript",
        json={
            "token": token, "transcript": [], "score": 5.0, "duration_s": 30.0,
        },
    )
    assert resp.status_code == 404
