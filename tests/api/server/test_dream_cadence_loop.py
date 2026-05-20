"""Optional autonomous cadence loop. Off-by-default; opt in via env."""
import asyncio
from collections import deque
from unittest.mock import AsyncMock, MagicMock

import pytest


class _FakeDomainMemory:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


@pytest.mark.asyncio
async def test_cadence_loop_no_op_when_heartbeat_zero(monkeypatch):
    """heartbeat_seconds<=0 must return immediately without consolidating."""
    from api.server.state import _run_dream_pass_cadence
    import api.server.services.memory.dream_consolidator as consolidator
    import api.server.routes.dream_pass_pause as pause

    monkeypatch.setattr(pause, "is_paused", lambda domain: False)
    consolidate = AsyncMock()
    monkeypatch.setattr(consolidator, "consolidate_memories", consolidate)

    orchestrator = MagicMock()
    await asyncio.wait_for(
        _run_dream_pass_cadence(
            orchestrator,
            domains=("hiring",),
            heartbeat_seconds=0,
            domain_memories={"hiring": _FakeDomainMemory(count=1)},
        ),
        timeout=1.0,
    )
    consolidate.assert_not_called()


@pytest.mark.asyncio
async def test_cadence_loop_fires_consolidation_and_records_history(monkeypatch):
    """Backlog-triggered cadence runs consolidate_memories and appends history."""
    from api.server.state import _run_dream_pass_cadence
    import api.server.routes.memory_v2 as mv2
    import api.server.routes.dream_pass_pause as pause
    import api.server.services.memory.dream_consolidator as consolidator

    monkeypatch.setattr(pause, "is_paused", lambda domain: False)
    history = deque(maxlen=50)
    monkeypatch.setattr(mv2, "_dream_history", history)
    monkeypatch.setattr(mv2, "_build_llm_consolidator", lambda domain: AsyncMock())

    store = _FakeDomainMemory(count=1)
    result = {"domain": "hiring", "input_count": 1, "output_count": 1}

    async def _fake_consolidate(*, domain_memory, llm_consolidate):
        assert domain_memory is store
        store._count = 0
        return result

    monkeypatch.setattr(consolidator, "consolidate_memories", _fake_consolidate)

    task = asyncio.create_task(
        _run_dream_pass_cadence(
            MagicMock(),
            domains=("hiring",),
            heartbeat_seconds=999,
            tick_seconds=1,
            backlog_threshold=1,
            domain_memories={"hiring": store},
        )
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert list(history) == [result]


@pytest.mark.asyncio
async def test_cadence_loop_continues_after_missing_domain_store(monkeypatch):
    """A missing store for one domain must not block a later valid domain."""
    from api.server.state import _run_dream_pass_cadence
    import api.server.routes.memory_v2 as mv2
    import api.server.routes.dream_pass_pause as pause
    import api.server.services.memory.dream_consolidator as consolidator

    monkeypatch.setattr(pause, "is_paused", lambda domain: False)
    monkeypatch.setattr(mv2, "_dream_history", deque(maxlen=50))
    monkeypatch.setattr(mv2, "_build_llm_consolidator", lambda domain: AsyncMock())

    store = _FakeDomainMemory(count=1)
    consolidate = AsyncMock(return_value={"domain": "hiring"})
    monkeypatch.setattr(consolidator, "consolidate_memories", consolidate)

    task = asyncio.create_task(
        _run_dream_pass_cadence(
            MagicMock(),
            domains=("does-not-exist", "hiring"),
            heartbeat_seconds=999,
            tick_seconds=1,
            backlog_threshold=1,
            domain_memories={"hiring": store},
        )
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert consolidate.await_count >= 1
    assert consolidate.await_args_list[0].kwargs["domain_memory"] is store
