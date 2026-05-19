from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes.dream_pass_exceptions import router


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def test_list_flagged_returns_repo_items(client) -> None:
    fake_repo = MagicMock()
    fake_repo.list_flagged.return_value = [
        {
            "lesson_id": "L-1",
            "body": "x",
            "proposed_by": "dp:hiring",
            "flag_reason": "implausible_delta",
            "delta": 0.25,
            "n_samples": 40,
            "experiment": None,
            "proposed_at": "2026-05-19T10:00:00+00:00",
        }
    ]
    with patch("api.server.routes.dream_pass_exceptions._repo", return_value=fake_repo):
        resp = client.get("/api/dream-pass/flagged?domain=hiring")

    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["lesson_id"] == "L-1"
    assert body["items"][0]["flag_reason"] == "implausible_delta"
    fake_repo.list_flagged.assert_called_once_with(domain="hiring")


def test_list_flagged_requires_domain_query(client) -> None:
    fake_repo = MagicMock()
    with patch("api.server.routes.dream_pass_exceptions._repo", return_value=fake_repo):
        resp = client.get("/api/dream-pass/flagged")
    assert resp.status_code == 422


def test_approve_calls_governor(client) -> None:
    fake_gov = MagicMock()
    with patch("api.server.routes.dream_pass_exceptions._governor", return_value=fake_gov):
        resp = client.post(
            "/api/dream-pass/flagged/L-1/approve",
            json={"approver": "alice@example.com"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "approved", "lesson_id": "L-1"}
    fake_gov.approve_flagged.assert_called_once_with(
        lesson_id="L-1", approver="alice@example.com"
    )


def test_approve_returns_404_when_missing(client) -> None:
    fake_gov = MagicMock()
    fake_gov.approve_flagged.side_effect = LookupError("no candidate lesson found with id L-NOPE")
    with patch("api.server.routes.dream_pass_exceptions._governor", return_value=fake_gov):
        resp = client.post(
            "/api/dream-pass/flagged/L-NOPE/approve",
            json={"approver": "alice@example.com"},
        )
    assert resp.status_code == 404


def test_reject_calls_governor(client) -> None:
    fake_gov = MagicMock()
    with patch("api.server.routes.dream_pass_exceptions._governor", return_value=fake_gov):
        resp = client.post(
            "/api/dream-pass/flagged/L-1/reject",
            json={"reviewer": "alice@example.com", "reason": "contradicts policy"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "rejected", "lesson_id": "L-1"}
    fake_gov.reject_flagged.assert_called_once_with(
        lesson_id="L-1", reviewer="alice@example.com", reason="contradicts policy"
    )


def test_reject_requires_non_empty_reason(client) -> None:
    fake_gov = MagicMock()
    with patch("api.server.routes.dream_pass_exceptions._governor", return_value=fake_gov):
        resp = client.post(
            "/api/dream-pass/flagged/L-1/reject",
            json={"reviewer": "alice@example.com", "reason": ""},
        )
    assert resp.status_code == 422
    fake_gov.reject_flagged.assert_not_called()
