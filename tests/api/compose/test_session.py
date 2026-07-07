import asyncio
import pytest
from api.server.services.compose.session import ComposeSession


@pytest.mark.asyncio
async def test_subscribe_receives_live_events():
    s = ComposeSession("abc")
    q = s.subscribe()
    s.emit({"type": "thought", "text": "hi"})
    assert await asyncio.wait_for(q.get(), timeout=1) == {"type": "thought", "text": "hi"}


@pytest.mark.asyncio
async def test_late_subscriber_replays_buffered_events():
    s = ComposeSession("abc")
    s.emit({"type": "narration", "text": "first"})
    q = s.subscribe()  # subscribed AFTER the emit
    assert await asyncio.wait_for(q.get(), timeout=1) == {"type": "narration", "text": "first"}


def test_stage_event_updates_current_stage():
    s = ComposeSession("abc")
    assert s.stage == "intake"
    s.emit({"type": "stage", "stage": "composing", "label": "Composing"})
    assert s.stage == "composing"


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    s = ComposeSession("abc")
    q = s.subscribe()
    s.unsubscribe(q)
    s.emit({"type": "thought", "text": "ignored"})
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.get(), timeout=0.2)


@pytest.mark.asyncio
async def test_pending_future_resolves():
    s = ComposeSession("cid")
    fut = s.new_pending("req1")
    assert not fut.done()
    s.resolve("req1", {"answer": "CFO"})
    assert await asyncio.wait_for(fut, timeout=1) == {"answer": "CFO"}


def test_resolve_unknown_request_is_noop():
    s = ComposeSession("cid")
    s.resolve("nope", {"x": 1})  # must not raise
