import asyncio
import sys
import pytest
from api.server.services.compose.session import ComposeSession
from api.server.services.compose.bridge import ComposeBridge

FAKE = ["tests/api/compose/fake_acp_agent.py"]


@pytest.mark.asyncio
async def test_agent_exit_midprompt_surfaces_error_not_hang(monkeypatch):
    monkeypatch.setenv("COMPOSE_RECORD", "0")
    monkeypatch.setenv("FAKE_ACP_TRACE", "tests/api/compose/fixtures/basic_trace.jsonl")
    monkeypatch.setenv("FAKE_ACP_EXIT_MIDPROMPT", "1")
    session = ComposeSession("cid")
    bridge = ComposeBridge(session, document_text="x", copilot_cmd=[sys.executable, *FAKE])
    await bridge.start()

    q = session.subscribe()
    seen = []
    # Must terminate (ready) within a few seconds — NOT hang.
    for _ in range(50):
        ev = await asyncio.wait_for(q.get(), timeout=8)
        seen.append(ev)
        if ev.get("type") == "stage" and ev.get("stage") == "ready":
            break
    types = [e["type"] for e in seen]
    assert "error" in types, f"expected an error event, got {types}"
    assert seen[-1]["stage"] == "ready"
    assert session.done is True
