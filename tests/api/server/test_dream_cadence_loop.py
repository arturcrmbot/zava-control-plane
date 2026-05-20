"""Optional autonomous cadence loop. Off-by-default; opt in via env."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_cadence_loop_no_op_when_interval_zero(monkeypatch):
    """interval_seconds<=0 must return immediately without dispatching."""
    monkeypatch.delenv("DREAM_PASS_DEMO_CADENCE_SECONDS", raising=False)
    from api.server.state import _run_dream_pass_cadence
    orchestrator = MagicMock()
    orchestrator.run_pass = AsyncMock()
    await asyncio.wait_for(
        _run_dream_pass_cadence(orchestrator, domains=("hiring",), interval_seconds=0),
        timeout=1.0,
    )
    orchestrator.run_pass.assert_not_called()


@pytest.mark.asyncio
async def test_cadence_loop_fires_at_least_once_then_sleeps():
    """interval_seconds>0 fires the pass, then sleeps; cancellation exits cleanly."""
    from api.server.state import _run_dream_pass_cadence
    orchestrator = MagicMock()
    orchestrator.run_pass = AsyncMock(return_value=MagicMock(promoted_lesson_ids=()))
    task = asyncio.create_task(_run_dream_pass_cadence(
        orchestrator, domains=("hiring",), interval_seconds=1,
    ))
    await asyncio.sleep(0.3)  # let one cycle through
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert orchestrator.run_pass.call_count >= 1


@pytest.mark.asyncio
async def test_cadence_loop_continues_after_a_domain_error():
    """A skill-load failure for one domain must not stop subsequent domains."""
    from api.server.state import _run_dream_pass_cadence
    orchestrator = MagicMock()
    orchestrator.run_pass = AsyncMock(return_value=MagicMock(promoted_lesson_ids=()))
    task = asyncio.create_task(_run_dream_pass_cadence(
        orchestrator,
        domains=("does-not-exist", "hiring"),
        interval_seconds=1,
    ))
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # The known-good domain (hiring) must still have been called.
    called_skills = [c.kwargs.get("skill") for c in orchestrator.run_pass.call_args_list]
    assert any(getattr(s, "domain", None) == "hiring" for s in called_skills)
