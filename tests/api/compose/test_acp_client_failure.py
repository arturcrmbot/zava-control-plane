import sys
import pytest
from api.server.services.compose.acp_client import AcpClient

FAKE = ["tests/api/compose/fake_acp_agent.py"]


@pytest.mark.asyncio
async def test_request_raises_when_agent_exits_before_reply(monkeypatch):
    monkeypatch.setenv("FAKE_ACP_TRACE", "tests/api/compose/fixtures/basic_trace.jsonl")
    monkeypatch.setenv("FAKE_ACP_EXIT_MIDPROMPT", "1")

    async def on_notify(method, params): pass
    async def on_request(method, params): return {}

    client = AcpClient(on_notify, on_request)
    await client.start([sys.executable, *FAKE, "--acp"], cwd=".")
    await client.request("initialize", {"protocolVersion": 1})
    new = await client.request("session/new", {"cwd": "."})
    assert new["sessionId"] == "fake-session"
    # agent emits one update then exits without replying to prompt -> must raise, not hang
    with pytest.raises(ConnectionError):
        await client.request("session/prompt", {"sessionId": "fake-session", "prompt": []})
    await client.stop()
