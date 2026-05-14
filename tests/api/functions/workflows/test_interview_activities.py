"""Phase 7 sub-wait activities. Mirrors voice_screen_activities tests —
direct function calls with monkeypatched app_state so the graph stack
isn't loaded."""
from unittest.mock import MagicMock

import pytest

from api.functions.workflows import interview_activities


@pytest.fixture
def fake_app_state(monkeypatch):
    state = MagicMock()
    state.magic_links.issue.return_value = "TOKEN-123"
    state.email_sender.send.return_value = "msg-id-1"
    state.store.get_candidate.return_value = {
        "id": "C-1", "name": "Alex", "email": "alex@example.com",
    }
    monkeypatch.setattr(
        "api.functions.workflows.interview_activities.app_state",
        state, raising=False,
    )
    # Make the import-time `from api.server.state import app_state` lookup
    # also resolve to our fake.
    import api.server.state as ss
    monkeypatch.setattr(ss, "app_state", state)
    return state


def test_issue_book_interview_link_returns_token_and_url(fake_app_state):
    out = interview_activities.issue_book_interview_link_activity({
        "candidate_id": "C-1",
    })
    fake_app_state.magic_links.issue.assert_called_once()
    kwargs = fake_app_state.magic_links.issue.call_args.kwargs
    assert kwargs["scope"] == "book_interview"
    assert kwargs["single_use"] is True
    assert kwargs["ttl_seconds"] == 7 * 24 * 3600
    assert out["token"] == "TOKEN-123"
    assert out["portal_url"].endswith("/book?token=TOKEN-123")


def test_send_book_interview_email_sends_and_records(fake_app_state):
    out = interview_activities.send_book_interview_email_activity({
        "candidate_id": "C-1",
        "token": "TOKEN-123",
        "portal_url": "http://localhost:5274/book?token=TOKEN-123",
        "role_title": "Senior Data Engineer",
    })
    fake_app_state.email_sender.send.assert_called_once()
    sent = fake_app_state.email_sender.send.call_args.kwargs
    assert sent["to"] == "alex@example.com"
    assert "interview" in sent["subject"].lower()
    assert "TOKEN-123" in sent["html_body"]
    assert "Senior Data Engineer" in sent["html_body"]
    assert out["sent"] is True


def test_send_book_interview_email_no_candidate(fake_app_state):
    fake_app_state.store.get_candidate.return_value = None
    out = interview_activities.send_book_interview_email_activity({
        "candidate_id": "C-MISSING",
        "token": "T",
    })
    assert out == {"sent": False, "reason": "unknown_candidate"}
    fake_app_state.email_sender.send.assert_not_called()


def test_send_rejection_email_interview_gate(fake_app_state):
    out = interview_activities.send_rejection_email_activity({
        "candidate_id": "C-1",
        "gate": "interview",
        "role_title": "Senior Data Engineer",
    })
    sent = fake_app_state.email_sender.send.call_args.kwargs
    assert "Senior Data Engineer" in sent["html_body"]
    assert "interview" in sent["html_body"].lower()
    assert out["sent"] is True


def test_send_rejection_email_offer_gate(fake_app_state):
    interview_activities.send_rejection_email_activity({
        "candidate_id": "C-1",
        "gate": "offer",
        "role_title": "Senior Data Engineer",
    })
    sent = fake_app_state.email_sender.send.call_args.kwargs
    # Offer-gate copy specifically mentions interview-stage feedback
    assert "after the interview" in sent["html_body"].lower() or "interview stage" in sent["html_body"].lower()


def test_recommender_activity_runs_executor(fake_app_state, monkeypatch):
    """Activity is a thin asyncio.run wrapper around the executor — verify it
    forwards payload + returns the executor's dict."""
    async def fake_execute(payload):
        return {"interview_recommender": {"decision": "advance"}}

    import api.functions.graphs.executors.agents.agent_interview_recommender as agent
    monkeypatch.setattr(agent, "execute", fake_execute)

    out = interview_activities.hiring_interview_recommender_activity({
        "workflow_id": "WF", "gate": "post_voice",
    })
    assert out == {"interview_recommender": {"decision": "advance"}}
