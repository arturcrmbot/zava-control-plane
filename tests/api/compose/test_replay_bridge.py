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


@pytest.mark.asyncio
async def test_replay_backfills_parsed_on_brief_events():
    """A tape recorded before the projection existed should still drive the
    canvas: replay derives `parsed` from the brief yaml."""
    yaml = (
        "domain:\n"
        "  workflow_type: demo-flow\n"
        "  display_name: Demo flow\n"
        "phases:\n"
        "  - name: intake\n"
        "    intent: Capture it.\n"
        "    kind: deterministic\n"
        "function: ops\n"
    )
    tape = [{"ts_offset_ms": 0, "event": {"type": "brief", "yaml": yaml}}]
    s = ComposeSession("cid")
    q = s.subscribe()
    await ReplayBridge(s, tape, speed=1000.0).start()
    brief = None
    for _ in range(10):
        ev = await asyncio.wait_for(q.get(), timeout=2)
        if ev.get("type") == "brief":
            brief = ev
            break
    assert brief is not None
    assert brief["parsed"]["workflowType"] == "demo-flow"
    assert brief["parsed"]["steps"][0]["name"] == "Intake"
