import asyncio
import pytest
from api.server.services.compose import registry
from api.server.services.compose.session import ComposeSession
from api.server.routes.compose import resolve_answer, resolve_brief


@pytest.mark.asyncio
async def test_resolve_answer_sets_future():
    registry.reset()
    s = ComposeSession("cid")
    registry.register(s)
    fut = s.new_pending("r1")
    await resolve_answer("cid", {"request_id": "r1", "answer": "CFO"})
    assert await asyncio.wait_for(fut, timeout=1) == "CFO"


@pytest.mark.asyncio
async def test_resolve_brief_sets_future_with_edit():
    registry.reset()
    s = ComposeSession("cid")
    registry.register(s)
    fut = s.new_pending("r2")
    await resolve_brief("cid", {"request_id": "r2", "approved": True, "yaml": "edited"})
    assert await asyncio.wait_for(fut, timeout=1) == {"approved": True, "yaml": "edited"}


@pytest.mark.asyncio
async def test_resolve_answer_emits_question_cleared():
    registry.reset()
    s = ComposeSession("cid")
    registry.register(s)
    s.new_pending("r1")
    await resolve_answer("cid", {"request_id": "r1", "answer": "CFO"})
    assert any(e.get("type") == "question_cleared" and e.get("request_id") == "r1"
               for e in s.events)


@pytest.mark.asyncio
async def test_resolve_brief_emits_brief_cleared():
    registry.reset()
    s = ComposeSession("cid")
    registry.register(s)
    s.new_pending("r2")
    await resolve_brief("cid", {"request_id": "r2", "approved": True, "yaml": "x"})
    assert any(e.get("type") == "brief_cleared" and e.get("request_id") == "r2"
               for e in s.events)
