from __future__ import annotations

import asyncio
import contextlib
from dataclasses import replace
from importlib import import_module
from types import SimpleNamespace

import pytest

from api.server.services.event_bus import EventBus
from api.server.state import app_state
from api.server.world.registry import resolve_world_pack
from api.server.world.service import ActorWorldService
from api.shared.vertical_loader import build_runtime
from api.shared.world_contracts import WorldScaleProfile
from verticals.telco.world import NetworkConfig, NetworkScenario


class _ResettableWorldService:
    def __init__(self) -> None:
        self.seed = 42
        self.runtime = SimpleNamespace(now=0)
        self.reset_calls: list[int] = []
        self.run_calls = 0
        self.run_started = asyncio.Event()

    def reset(self, seed: int) -> None:
        self.seed = seed
        self.reset_calls.append(seed)

    async def run(self) -> None:
        self.run_calls += 1
        self.run_started.set()
        await asyncio.Future()


async def _cancel_task(task: asyncio.Task | None) -> None:
    if task is None or task.done():
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_scene_route_returns_the_active_pack_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = import_module("api.server.routes.world")
    handler = getattr(routes, "world_scene", None)
    assert callable(handler)
    scene = {
        "schema_version": 1,
        "title": "Demo",
        "locations": [{"id": "LOC-1"}],
        "layers": [{"state_key": "people"}],
        "event_mappings": [{"event_type": "person.moved"}],
    }
    service = SimpleNamespace(
        registration=SimpleNamespace(scene=scene),
    )
    monkeypatch.setattr(app_state, "world_service", service, raising=False)

    assert await handler() == {"enabled": True, **scene}


@pytest.mark.asyncio
async def test_reset_route_reinstalls_seeded_world(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = import_module("api.server.routes.world")
    handler = getattr(routes, "reset_world", None)
    request_type = getattr(routes, "WorldResetRequest", None)
    assert callable(handler)
    assert request_type is not None
    lifecycle: list[str] = []
    service = SimpleNamespace(
        seed=42,
        runtime=SimpleNamespace(now=0),
        reset=lambda seed: lifecycle.append(f"reset:{seed}"),
    )
    bridge = SimpleNamespace(
        stop=lambda: lifecycle.append("bridge:stop"),
        start=lambda: lifecycle.append("bridge:start"),
    )
    monkeypatch.setattr(app_state, "world_service", service, raising=False)
    monkeypatch.setattr(app_state, "world_bridge", bridge, raising=False)
    running_task = asyncio.current_task()
    monkeypatch.setattr(app_state, "world_task", running_task, raising=False)

    result = await handler(request_type(seed=7))

    assert lifecycle == ["bridge:stop", "reset:7", "bridge:start"]
    assert result == {"ok": True, "seed": 7, "sim_time": 0}
    assert app_state.world_task is running_task


@pytest.mark.asyncio
async def test_reset_route_clears_active_pack_workflows_before_reseeding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = import_module("api.server.routes.world")
    lifecycle: list[str] = []
    service = SimpleNamespace(
        seed=42,
        runtime=SimpleNamespace(now=0),
        reset=lambda seed: lifecycle.append(f"reset:{seed}"),
    )
    bridge = SimpleNamespace(
        stop=lambda: lifecycle.append("bridge:stop"),
        start=lambda: lifecycle.append("bridge:start"),
    )
    store = SimpleNamespace(
        clear_workflows=lambda workflow_types: (
            lifecycle.append(
                "store:clear:" + ",".join(sorted(workflow_types))
            )
            or {"REBAL-1"}
        )
    )
    runtime = SimpleNamespace(
        pack=SimpleNamespace(
            domains={
                "inventory-rebalancing": object(),
                "demand-spike-response": object(),
            }
        )
    )
    monkeypatch.setattr(app_state, "world_service", service, raising=False)
    monkeypatch.setattr(app_state, "world_bridge", bridge, raising=False)
    monkeypatch.setattr(app_state, "world_task", asyncio.current_task(), raising=False)
    monkeypatch.setattr(app_state, "store", store, raising=False)
    monkeypatch.setattr(app_state, "runtime", runtime, raising=False)
    monkeypatch.setattr(
        app_state,
        "orchestration_history",
        {"REBAL-1": [{"kind": "workflow.completed"}]},
        raising=False,
    )

    result = await routes.reset_world(routes.WorldResetRequest(seed=42))

    assert lifecycle == [
        "bridge:stop",
        "store:clear:demand-spike-response,inventory-rebalancing",
        "reset:42",
        "bridge:start",
    ]
    assert app_state.orchestration_history == {}
    assert result["ok"] is True
@pytest.mark.asyncio
async def test_reset_route_starts_one_runner_when_task_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = import_module("api.server.routes.world")
    service = _ResettableWorldService()
    lifecycle: list[str] = []
    bridge = SimpleNamespace(
        stop=lambda: lifecycle.append("bridge:stop"),
        start=lambda: lifecycle.append("bridge:start"),
    )
    monkeypatch.setattr(app_state, "world_service", service, raising=False)
    monkeypatch.setattr(app_state, "world_bridge", bridge, raising=False)
    monkeypatch.setattr(app_state, "world_task", None, raising=False)

    task = None
    try:
        await routes.reset_world(routes.WorldResetRequest())
        task = app_state.world_task
        await asyncio.wait_for(service.run_started.wait(), timeout=1)
        await routes.reset_world(routes.WorldResetRequest())

        assert task is not None
        assert app_state.world_task is task
        assert service.run_calls == 1
        assert service.reset_calls == [42, 42]
        assert lifecycle == [
            "bridge:stop",
            "bridge:start",
            "bridge:stop",
            "bridge:start",
        ]
    finally:
        await _cancel_task(task)


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_state", ["completed", "cancelled"])
async def test_reset_route_replaces_a_finished_runner(
    monkeypatch: pytest.MonkeyPatch,
    terminal_state: str,
) -> None:
    routes = import_module("api.server.routes.world")
    service = _ResettableWorldService()
    bridge = SimpleNamespace(stop=lambda: None, start=lambda: None)
    if terminal_state == "completed":
        old_task = asyncio.create_task(asyncio.sleep(0))
        await old_task
    else:
        old_task = asyncio.create_task(asyncio.Event().wait())
        old_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await old_task
    monkeypatch.setattr(app_state, "world_service", service, raising=False)
    monkeypatch.setattr(app_state, "world_bridge", bridge, raising=False)
    monkeypatch.setattr(app_state, "world_task", old_task, raising=False)

    replacement = None
    try:
        await routes.reset_world(routes.WorldResetRequest(seed=7))
        replacement = app_state.world_task
        await asyncio.wait_for(service.run_started.wait(), timeout=1)

        assert replacement is not old_task
        assert replacement is not None
        assert not replacement.done()
        assert service.run_calls == 1
    finally:
        await _cancel_task(replacement)


@pytest.mark.asyncio
async def test_reset_restarts_completed_real_telco_world_and_advances_injection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    routes = import_module("api.server.routes.world")
    vertical = build_runtime({"ZAVA_VERTICAL": "telco"}, data_root=tmp_path)
    registration = resolve_world_pack(vertical, "telco")
    short_scale = WorldScaleProfile(
        name="test",
        build_scenario=lambda runtime: NetworkScenario(
            runtime,
            NetworkConfig(
                site_count=4,
                subscriber_count=20,
                session_count=20,
                simulation_minutes=2,
            ),
        ),
        default_minutes_per_second=1_000_000,
    )
    service = ActorWorldService(
        seed=42,
        bus=EventBus(),
        vertical_runtime=vertical,
        registration=replace(
            registration,
            scales={"test": short_scale},
            default_scale="test",
        ),
        scale_name="test",
    )
    old_task = asyncio.create_task(service.run())
    await asyncio.wait_for(old_task, timeout=1)
    assert old_task.done()

    published: list[str] = []
    site_failed = asyncio.Event()

    def record(event) -> None:
        published.append(event.type)
        if event.type == "world.site.failed":
            site_failed.set()

    service.bus.on_any(record)
    bridge = SimpleNamespace(stop=lambda: None, start=lambda: None)
    monkeypatch.setattr(app_state, "world_service", service, raising=False)
    monkeypatch.setattr(app_state, "world_bridge", bridge, raising=False)
    monkeypatch.setattr(app_state, "world_task", old_task, raising=False)

    replacement = None
    try:
        await routes.reset_world(routes.WorldResetRequest(seed=7))
        replacement = app_state.world_task
        assert replacement is not old_task
        assert service._published_seq == len(service.runtime.journal)

        result = await routes.inject_site_failure(routes.SiteFailureRequest(site_id="SITE-01"))
        await asyncio.wait_for(site_failed.wait(), timeout=1)

        assert result["ok"] is True
        assert service.scenario.sites["SITE-01"].status == "failed"
        assert any(event.type == "site.failed" for event in service.runtime.journal)
        assert "world.simulation.started" not in published
    finally:
        service.stop()
        await _cancel_task(replacement)
