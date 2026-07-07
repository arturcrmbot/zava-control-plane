import asyncio
import sys
import pytest
from api.server.services.compose.session import ComposeSession
from api.server.services.compose.bridge import ComposeBridge

FAKE = ["tests/api/compose/fake_acp_agent.py"]


@pytest.mark.asyncio
async def test_bridge_streams_translated_events_then_ready(monkeypatch):
    monkeypatch.setenv("COMPOSE_RECORD", "0")
    monkeypatch.setenv("FAKE_ACP_TRACE", "tests/api/compose/fixtures/basic_trace.jsonl")
    session = ComposeSession("cid1")
    bridge = ComposeBridge(
        session, document_text="A capex approval process.",
        copilot_cmd=[sys.executable, *FAKE],
    )
    await bridge.start()

    # Collect until we hit the terminal 'ready' stage (bridge sets it after prompt).
    collected: list[dict] = []
    q = session.subscribe()
    for _ in range(50):
        ev = await asyncio.wait_for(q.get(), timeout=5)
        collected.append(ev)
        if ev.get("type") == "stage" and ev.get("stage") == "ready":
            break

    types = [e["type"] for e in collected]
    assert "thought" in types
    assert "tool" in types
    assert "narration" in types
    assert collected[-1] == {"type": "stage", "stage": "ready", "label": "Run complete"}
    assert session.done is True
