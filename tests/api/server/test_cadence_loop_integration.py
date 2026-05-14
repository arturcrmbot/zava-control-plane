"""Phase 4 IP1 — narrative integration test for the cadence loop.

Boots a test ``AppState`` with a `* * * * *` cadence pointed at a stub
ambient agent, advances time via a monkeypatched ``croniter.get_next``
that returns a near-immediate timestamp, and asserts:

  (a) one ``cadence.tick`` audit event fires;
  (b) the dispatcher's ``dispatch`` was awaited with the expected
      ``trigger_ctx`` (``kind="cadence"`` + ``cadence_name``).
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import importlib
from pathlib import Path

import pytest

from api.server.services.cadence_loader import Cadence


pytestmark = pytest.mark.asyncio


async def _build_app_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    import api.server.state as state_mod
    importlib.reload(state_mod)
    await state_mod.app_state.aclose()
    state = state_mod.AppState()
    return state, state_mod


async def test_cadence_tick_fires_dispatch_and_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    state, _state_mod = await _build_app_state(tmp_path, monkeypatch)

    # Patch the dispatch so we don't need a real ambient agent name to
    # be wired into AMBIENT_AGENTS — record the call args instead.
    calls: list[tuple[str, dict]] = []

    async def _fake_dispatch(name: str, trigger_ctx: dict):
        calls.append((name, trigger_ctx))

    # Initialise function FMs first so ambient_dispatcher exists.
    state.init_function_fms()
    state.ambient_dispatcher.dispatch = _fake_dispatch  # type: ignore[assignment]

    # Make croniter return ~100ms in the future every call.
    import api.server.state as state_mod
    real_croniter = state_mod  # placeholder

    class _FastCron:
        def __init__(self, schedule, base):
            pass
        def get_next(self, _ret):
            return _dt.datetime.now() + _dt.timedelta(milliseconds=80)

    # Patch the croniter symbol the loop imports inside _run_cadence.
    monkeypatch.setattr("croniter.croniter", _FastCron)

    # Drive a single cadence task directly (bypass the boot wiring so
    # we don't depend on ambient agent registration).
    fake_cad = Cadence(name="test-fast", schedule="* * * * *",
                       fires_ambient_agent="morning-sweep")
    task = asyncio.create_task(state._run_cadence(fake_cad))
    try:
        await asyncio.sleep(0.4)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # (a) at least one cadence.tick audit entry was logged.
    ticks = [e for e in state.audit.list() if e.get("action") == "cadence.tick"]
    assert ticks, f"no cadence.tick audit entries; got actions: {[e.get('action') for e in state.audit.list()]}"
    last = ticks[-1]
    assert last["details"]["cadence_name"] == "test-fast"
    assert last["details"]["ambient_agent"] == "morning-sweep"

    # (b) dispatch was called with trigger_ctx kind=cadence + cadence_name.
    assert calls, "ambient_dispatcher.dispatch was never awaited"
    name, ctx = calls[-1]
    assert name == "morning-sweep"
    assert ctx["kind"] == "cadence"
    assert ctx["cadence_name"] == "test-fast"
    assert "scheduled_for" in ctx

    await state.aclose()
