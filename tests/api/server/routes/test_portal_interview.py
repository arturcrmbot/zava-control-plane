"""Candidate-side booking endpoints. Use the existing FastAPI TestClient
fixture pattern from test_portal.py."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.server.main import app
from api.server.state import app_state


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    """Each test starts with a fresh in-memory store + a fresh sqlite db."""
    db_path = tmp_path / "ml.sqlite"
    from api.server.services.magic_link import MagicLinkStore
    monkeypatch.setattr(app_state, "magic_links", MagicLinkStore(db_path))
    app_state.store._candidates.clear()  # type: ignore[attr-defined]
    app_state.store._workflows.clear()   # type: ignore[attr-defined]
    yield


def _seed_candidate_with_token(scope: str = "book_interview"):
    cand_id = "C-TEST"
    app_state.store._candidates[cand_id] = {  # type: ignore[attr-defined]
        "id": cand_id, "name": "Alex", "email": "a@e.com",
        "role_id": "REQ-X", "instance_id": "DF-INSTANCE-1",
        "metadata_role_title": "Senior Data Engineer",
    }
    token = app_state.magic_links.issue(
        candidate_id=cand_id, scope=scope, ttl_seconds=3600, single_use=True,
    )
    return cand_id, token


def test_resolve_returns_candidate_role_and_slot_grid():
    cand_id, token = _seed_candidate_with_token()
    client = TestClient(app)
    resp = client.get(f"/api/portal/interview/resolve?token={token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_id"] == cand_id
    assert "role_title" in body
    # 5 weekdays × 3 slots = 15 entries
    slots = body["slots"]
    assert len(slots) == 15
    assert all("slot_id" in s and "starts_at" in s and "available" in s for s in slots)
    # Deterministic mask: same candidate, same response (modulo time).
    resp2 = client.get(f"/api/portal/interview/resolve?token={token}")
    assert resp.json()["slots"] == resp2.json()["slots"]


def test_resolve_404_on_unknown_token():
    client = TestClient(app)
    resp = client.get("/api/portal/interview/resolve?token=NOT-REAL")
    assert resp.status_code == 404


def test_resolve_404_on_wrong_scope():
    """A status-scope token must not resolve here."""
    _, token = _seed_candidate_with_token(scope="status")
    client = TestClient(app)
    resp = client.get(f"/api/portal/interview/resolve?token={token}")
    assert resp.status_code == 404


def test_book_consumes_token_and_raises_event():
    cand_id, token = _seed_candidate_with_token()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_interview.raise_orchestration_event",
        new=AsyncMock(),
    ) as mock_raise:
        resp = client.post(
            "/api/portal/interview/book",
            json={"token": token, "slot_id": "mon-09:00"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_raise.assert_awaited_once()
    args = mock_raise.await_args.args
    assert args[0] == "DF-INSTANCE-1"
    assert args[1] == "interview_booked"
    assert args[2]["candidate_id"] == cand_id
    assert args[2]["slot"]["slot_id"] == "mon-09:00"


def test_book_double_consume_returns_409():
    cand_id, token = _seed_candidate_with_token()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_interview.raise_orchestration_event",
        new=AsyncMock(),
    ):
        client.post("/api/portal/interview/book",
                    json={"token": token, "slot_id": "mon-09:00"})
        resp = client.post("/api/portal/interview/book",
                           json={"token": token, "slot_id": "tue-13:00"})
    assert resp.status_code == 409


def test_book_unknown_slot_id_400():
    cand_id, token = _seed_candidate_with_token()
    client = TestClient(app)
    resp = client.post("/api/portal/interview/book",
                       json={"token": token, "slot_id": "sat-11:00"})
    assert resp.status_code == 400
