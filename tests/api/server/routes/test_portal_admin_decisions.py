"""Recruiter-side decision endpoints — the two HITL gates' resume points."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.server.main import app
from api.server.state import app_state


@pytest.fixture(autouse=True)
def reset_state():
    app_state.store._candidates.clear()  # type: ignore[attr-defined]
    yield


def _seed():
    app_state.store._candidates["C-1"] = {  # type: ignore[attr-defined]
        "id": "C-1", "instance_id": "DF-1",
    }


def test_interview_invite_invite_decision_raises_event():
    _seed()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_admin_decisions.raise_orchestration_event",
        new=AsyncMock(),
    ) as mock_raise:
        resp = client.post(
            "/api/portal/admin/candidate/C-1/interview-invite",
            json={"decision": "invite", "resolved_by": "recruiter@wpp"},
        )
    assert resp.status_code == 200
    args = mock_raise.await_args.args
    assert args[0] == "DF-1"
    assert args[1] == "interview_invite"
    assert args[2]["decision"] == "invite"
    assert args[2]["resolved_by"] == "recruiter@wpp"


def test_interview_invite_reject_decision_raises_event():
    _seed()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_admin_decisions.raise_orchestration_event",
        new=AsyncMock(),
    ) as mock_raise:
        resp = client.post(
            "/api/portal/admin/candidate/C-1/interview-invite",
            json={"decision": "reject", "reason": "below bar"},
        )
    assert resp.status_code == 200
    assert mock_raise.await_args.args[2]["decision"] == "reject"
    assert mock_raise.await_args.args[2]["reason"] == "below bar"


def test_interview_invite_400_on_invalid_decision():
    _seed()
    client = TestClient(app)
    resp = client.post(
        "/api/portal/admin/candidate/C-1/interview-invite",
        json={"decision": "maybe"},
    )
    assert resp.status_code == 400


def test_interview_invite_404_on_unknown_candidate():
    client = TestClient(app)
    resp = client.post(
        "/api/portal/admin/candidate/C-NOPE/interview-invite",
        json={"decision": "invite"},
    )
    assert resp.status_code == 404


def test_post_interview_offer_requires_level():
    _seed()
    client = TestClient(app)
    resp = client.post(
        "/api/portal/admin/candidate/C-1/post-interview-decision",
        json={"decision": "offer", "notes": "great", "rating": 4},
    )
    assert resp.status_code == 400
    assert "level" in resp.json()["detail"].lower()


def test_post_interview_offer_with_level_raises_event():
    _seed()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_admin_decisions.raise_orchestration_event",
        new=AsyncMock(),
    ) as mock_raise:
        resp = client.post(
            "/api/portal/admin/candidate/C-1/post-interview-decision",
            json={
                "decision": "offer", "level": "Senior",
                "notes": "strong on Spark", "rating": 5,
                "resolved_by": "recruiter@wpp",
            },
        )
    assert resp.status_code == 200
    args = mock_raise.await_args.args
    assert args[1] == "offer_decision"
    assert args[2]["decision"] == "offer"
    assert args[2]["level"] == "Senior"
    assert args[2]["rating"] == 5
    assert args[2]["notes"] == "strong on Spark"


def test_post_interview_reject_no_level_required():
    _seed()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_admin_decisions.raise_orchestration_event",
        new=AsyncMock(),
    ):
        resp = client.post(
            "/api/portal/admin/candidate/C-1/post-interview-decision",
            json={"decision": "reject", "notes": "weak", "rating": 2},
        )
    assert resp.status_code == 200


def test_post_interview_400_on_invalid_rating():
    _seed()
    client = TestClient(app)
    resp = client.post(
        "/api/portal/admin/candidate/C-1/post-interview-decision",
        json={"decision": "reject", "notes": "x", "rating": 9},
    )
    assert resp.status_code == 400
