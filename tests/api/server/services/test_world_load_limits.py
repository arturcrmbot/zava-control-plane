from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_bridge import WorldBridge
from api.server.world.service import ActorWorldService
from api.shared.vertical_loader import build_runtime


def _app_state(tmp_path):
    state = SimpleNamespace(
        bus=EventBus(),
        store=StateStore(),
        audit=SimpleNamespace(),
        hub=SimpleNamespace(),
        orchestration_history={},
        runtime=build_runtime({}, data_root=tmp_path),
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    return state


@pytest.mark.asyncio
async def test_world_bridge_caps_concurrent_work(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WORLD_MAX_IN_FLIGHT", "2")
    bridge = WorldBridge(_app_state(tmp_path))
    release = asyncio.Event()
    active = 0
    peak = 0
    started = 0

    async def work() -> None:
        nonlocal active, peak, started
        active += 1
        started += 1
        peak = max(peak, active)
        await release.wait()
        active -= 1

    for _ in range(3):
        bridge._spawn(work())
    tasks = tuple(bridge._tasks)
    await asyncio.sleep(0)

    assert started == 2
    assert peak == 2

    release.set()
    await asyncio.gather(*tasks)
    assert started == 3


@pytest.mark.asyncio
async def test_actor_world_caps_same_time_steps(monkeypatch) -> None:
    monkeypatch.setenv("WORLD_MAX_STEPS_PER_SECOND", "50")
    service = object.__new__(ActorWorldService)
    service._stop_requested = False
    service.minutes_per_second = 10.0
    service.runtime = SimpleNamespace(status="paused", now=0.0)

    def step_once() -> None:
        service.runtime.status = "completed"

    service._step_once = step_once
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("api.server.world.service.asyncio.sleep", record_sleep)

    await service.run()

    assert delays == [pytest.approx(0.02)]
