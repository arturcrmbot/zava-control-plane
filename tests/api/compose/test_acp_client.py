import sys
import pytest
from api.server.services.compose.acp_client import AcpClient

FAKE = ["tests/api/compose/fake_acp_agent.py"]


@pytest.mark.asyncio
async def test_initialize_and_session_new_roundtrip(monkeypatch):
    monkeypatch.setenv("FAKE_ACP_TRACE", "tests/api/compose/fixtures/basic_trace.jsonl")
    notifications = []

    async def on_notify(method, params):
        notifications.append((method, params))

    async def on_request(method, params):
        return {}

    client = AcpClient(on_notify, on_request)
    await client.start([sys.executable, *FAKE, "--acp", "-C", ".", "--allow-all"], cwd=".")

    init = await client.request("initialize", {"protocolVersion": 1})
    assert init["protocolVersion"] == 1

    new = await client.request("session/new", {"cwd": "."})
    assert new["sessionId"] == "fake-session"

    await client.request("session/prompt", {"sessionId": "fake-session", "prompt": []})
    # the fake streamed 5 session/update notifications during the prompt
    assert sum(1 for m, _ in notifications if m == "session/update") == 5

    await client.stop()
