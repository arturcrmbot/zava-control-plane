"""Fleet Manager service wiring — bus → triage → queue → reasoning.

Covers the fix that lets `fleet.tick` (and other workflow-less wake events)
flow all the way through the pipeline to a `_process_batch` call, so the
demo rail pulses on idle runs instead of staying at "0 recent events".

We sidestep `start()` (which spawns the GHCP SDK subprocess) and instead
inject a fake session that just acknowledges `send_and_wait`.
"""
from __future__ import annotations
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.server.services.event_bus import EventBus
from api.server.services.fleet_manager_service import FleetManagerService
from api.shared.events import FleetEvent


class _FakeSession:
    """Minimal stand-in for a copilot session — `send_and_wait` returns a
    completion-like object so `_process_batch` can record `reasoning_done`."""

    async def send_and_wait(self, prompt: str, timeout: float = 120.0):
        return SimpleNamespace(data=SimpleNamespace(content="ok"))


@pytest.mark.asyncio
async def test_fleet_tick_drives_wakeup_and_reasoning_start():
    bus = EventBus()
    live_events: list[dict] = []

    fm = FleetManagerService(
        bus=bus,
        store=MagicMock(),
        audit=MagicMock(),
        on_live=live_events.append,
    )
    # Bypass start() — wire the bus subscription and inject a fake session.
    fm._session = _FakeSession()
    fm._unsub_bus = bus.on_any(fm._observe)
    # Speed up the debounce so the test doesn't have to wait 2s.
    fm._queue._debounce = 0.05

    bus.emit(FleetEvent(type="fleet.tick"))

    # Wait past the debounce + a bit for _process_batch to run send_and_wait.
    await asyncio.sleep(0.2)

    kinds = [e["kind"] for e in live_events]
    assert "wakeup" in kinds, f"expected wakeup; got {kinds}"
    assert "reasoning_start" in kinds, f"expected reasoning_start; got {kinds}"
    assert kinds.index("wakeup") < kinds.index("reasoning_start")

    wakeup = next(e for e in live_events if e["kind"] == "wakeup")
    assert wakeup["data"]["workflow_id"] is None
    assert wakeup["data"]["reason"] == "fleet.tick"
