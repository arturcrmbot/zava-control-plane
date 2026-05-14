"""Tests for the ACS Email REST sender (with offline-outbox fallback).

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 2.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from api.server.services.email_send import EmailSender, EmailSendError


@pytest.fixture
def sender(tmp_path):
    return EmailSender(
        connection_string=(
            "endpoint=https://x.communication.azure.com/;accesskey=AAAA"
        ),
        sender_address="DoNotReply@demo.example",
        outbox_dir=tmp_path / "outbox",
    )


@respx.mock
def test_send_posts_to_acs_endpoint_and_returns_message_id(sender):
    respx.post("https://x.communication.azure.com/emails:send").mock(
        return_value=httpx.Response(
            202,
            json={"id": "msg-123", "status": "Running"},
            headers={"operation-location": "https://x.communication.azure.com/emails/operations/msg-123"},
        ),
    )
    msg_id = sender.send(to="alice@example.com", subject="Hi", html_body="<p>hi</p>")
    assert msg_id == "msg-123"
    assert (sender.outbox_dir / "msg-123.html").read_text(encoding="utf-8") == "<p>hi</p>"


@respx.mock
def test_send_raises_on_4xx(sender):
    respx.post("https://x.communication.azure.com/emails:send").mock(
        return_value=httpx.Response(400, json={"error": "bad"}),
    )
    with pytest.raises(EmailSendError):
        sender.send(to="alice@example.com", subject="Hi", html_body="<p>hi</p>")


def test_send_falls_back_to_outbox_when_unconfigured(tmp_path):
    sender = EmailSender(
        connection_string=None,
        sender_address=None,
        outbox_dir=tmp_path / "ob",
    )
    msg_id = sender.send(
        to="alice@example.com", subject="Hi", html_body="<p>hi</p>"
    )
    assert msg_id.startswith("local-")
    assert (sender.outbox_dir / f"{msg_id}.html").exists()


@respx.mock
def test_send_signs_request_with_required_acs_headers(sender):
    """The Authorization header must be HMAC-SHA256 with the documented
    SignedHeaders triplet, and we must send x-ms-date + x-ms-content-sha256."""
    captured: dict[str, httpx.Request] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["req"] = request
        return httpx.Response(202, json={"id": "msg-xyz"})

    respx.post("https://x.communication.azure.com/emails:send").mock(side_effect=_handler)
    sender.send(to="bob@example.com", subject="S", html_body="<p>b</p>")

    req = captured["req"]
    auth = req.headers["Authorization"]
    assert auth.startswith("HMAC-SHA256 ")
    assert "SignedHeaders=x-ms-date;host;x-ms-content-sha256" in auth
    assert "Signature=" in auth
    assert "x-ms-date" in req.headers
    assert "x-ms-content-sha256" in req.headers
