from unittest.mock import AsyncMock

import httpx
import pytest

from api.functions import webhook


async def _send(sync: bool, *, required: bool) -> None:
    args = ("WF-DELIVERY", "INSTANCE-DELIVERY", "suspended", {"phase": "Approve"})
    if sync:
        webhook.emit_sync(*args, required=required)
    else:
        await webhook.emit(*args, required=required)


@pytest.mark.parametrize("sync", [False, True])
@pytest.mark.parametrize("status", [401, 503])
async def test_required_delivery_rejects_http_errors(respx_mock, sync, status):
    respx_mock.post(webhook.WEBHOOK_URL).respond(status)
    with pytest.raises(httpx.HTTPStatusError):
        await _send(sync, required=True)


@pytest.mark.parametrize("sync", [False, True])
async def test_required_delivery_propagates_transport_failure(respx_mock, sync):
    respx_mock.post(webhook.WEBHOOK_URL).mock(side_effect=httpx.ConnectError("offline"))
    with pytest.raises(httpx.ConnectError, match="offline"):
        await _send(sync, required=True)


@pytest.mark.parametrize("sync", [False, True])
async def test_best_effort_delivery_logs_failure(respx_mock, caplog, sync):
    respx_mock.post(webhook.WEBHOOK_URL).respond(503)
    await _send(sync, required=False)
    assert "WF-DELIVERY" in caplog.text
    assert "suspended" in caplog.text


@pytest.mark.parametrize("sync", [False, True])
async def test_required_delivery_preserves_signed_envelope(respx_mock, sync):
    route = respx_mock.post(webhook.WEBHOOK_URL).respond(200, json={"received": True})
    await _send(sync, required=True)
    request = route.calls.last.request
    assert len(request.headers["X-Durable-Event-Signature"]) == 64
    assert b'"workflow_id": "WF-DELIVERY"' in request.content


def test_checkpoint_uses_required_delivery(monkeypatch):
    from api.functions.workflows import activities

    emit = AsyncMock()
    monkeypatch.setattr(activities, "emit", emit)
    activities.checkpoint_activity({
        "workflow_id": "WF-DELIVERY",
        "instance_id": "INSTANCE-DELIVERY",
        "kind": "suspended",
        "payload": {"phase": "Approve"},
    })
    emit.assert_awaited_once_with(
        "WF-DELIVERY", "INSTANCE-DELIVERY", "suspended",
        {"phase": "Approve"}, required=True,
    )
