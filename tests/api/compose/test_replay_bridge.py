import asyncio
import pytest
from api.server.services.compose.session import ComposeSession
from api.server.services.compose.replay_bridge import ReplayBridge


TAPE = [
    {"ts_offset_ms": 0, "event": {"type": "thought", "text": "thinking"}},
    {"ts_offset_ms": 50, "event": {"type": "tool", "id": "t1", "title": "Reading x", "status": "completed"}},
    {"ts_offset_ms": 100, "event": {"type": "narration", "text": "done"}},
]


@pytest.mark.asyncio
async def test_replays_events_in_order_then_ready():
    s = ComposeSession("cid")
    q = s.subscribe()
    await ReplayBridge(s, TAPE, speed=1000.0).start()
    seen = []
    for _ in range(10):
        ev = await asyncio.wait_for(q.get(), timeout=2)
        seen.append(ev)
        if ev.get("type") == "stage" and ev.get("stage") == "ready":
            break
    types = [e.get("type") for e in seen]
    assert types[:3] == ["thought", "tool", "narration"]
    assert seen[-1]["stage"] == "ready"
    assert s.done is True


@pytest.mark.asyncio
async def test_pause_on_hitl_waits_for_answer():
    tape = [
        {"ts_offset_ms": 0, "event": {"type": "question", "request_id": "orig", "text": "CFO?", "options": ["CFO"]}},
        {"ts_offset_ms": 10, "event": {"type": "narration", "text": "after answer"}},
    ]
    s = ComposeSession("cid")
    q = s.subscribe()
    await ReplayBridge(s, tape, speed=1000.0, pause_on_hitl=True).start()

    first = await asyncio.wait_for(q.get(), timeout=2)
    assert first["type"] == "question"
    rid = first["request_id"]  # a fresh id assigned by replay
    # narration must NOT arrive until we answer
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.get(), timeout=0.3)
    s.resolve(rid, "CFO")
    nxt = await asyncio.wait_for(q.get(), timeout=2)
    assert nxt["type"] == "narration"
