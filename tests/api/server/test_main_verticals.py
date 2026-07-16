from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace

import pytest

from api.server.main import app, lifespan
from api.server.services.replay.player import current_player, set_active_player
from api.server.state import app_state


async def _sleep_forever() -> None:
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        raise


def _patch_live_lifespan_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.server import main as main_module
    from api.server.eval import online_subscriber as online_subscriber_module
    from api.server.routes import blueprint as blueprint_module
    from api.server.routes import whats_new as whats_new_module
    from api.server.services import persona_responder as persona_responder_module
    from api.server.services import portal_orchestration as portal_orchestration_module
    from api.server.services.ambient_agents import (
        auto_block_rule_learner,
        brand_budget_watcher,
        kpi_history_recorder,
        story_pack_writer,
        subsidiary_capacity_watcher,
        talent_transfer_cascade as talent_transfer_cascade_module,
        trend_cadence_watcher,
        vendor_block_watcher,
    )

    async def fake_fm_start() -> None:
        return None

    async def fake_fm_stop() -> None:
        return None

    async def fake_ramp_loop(_runtime=None) -> None:
        await _sleep_forever()

    async def fake_register(_app) -> None:
        return None

    async def fake_shutdown(_app) -> None:
        return None

    @asynccontextmanager
    async def fake_mcp_session_manager():
        yield

    def fake_attach(*_args, **_kwargs):
        return lambda: None

    class FakeTalentTransferCascade:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def start(self) -> None:
            return None

        def aclose(self) -> None:
            return None

    monkeypatch.delenv("ZAVA_MODE", raising=False)
    monkeypatch.delenv("ZAVA_TAPE_PATH", raising=False)
    monkeypatch.setenv("DREAM_PASS_DEMO_CADENCE_SECONDS", "0")
    monkeypatch.setattr(main_module.app_state.fm, "start", fake_fm_start)
    monkeypatch.setattr(main_module.app_state.fm, "stop", fake_fm_stop)
    monkeypatch.setattr(main_module.simulator_orchestrator, "ramp_loop", fake_ramp_loop)
    monkeypatch.setattr(main_module, "story_pack_writer", SimpleNamespace(start=lambda: None, stop=lambda: None), raising=False)
    monkeypatch.setattr(main_module, "_whats_new_attach", lambda _bus: lambda: None)
    monkeypatch.setattr(main_module.compose_mcp.session_manager, "run", fake_mcp_session_manager)
    monkeypatch.setattr(online_subscriber_module, "lifespan_register", fake_register)
    monkeypatch.setattr(online_subscriber_module, "lifespan_shutdown", fake_shutdown)
    monkeypatch.setattr(portal_orchestration_module, "attach", fake_attach)
    monkeypatch.setattr(persona_responder_module, "attach", fake_attach)
    monkeypatch.setattr(whats_new_module, "attach_to_bus", lambda _bus: lambda: None)
    monkeypatch.setattr(blueprint_module, "demo_stream_start", fake_register)
    monkeypatch.setattr(talent_transfer_cascade_module, "TalentTransferCascade", FakeTalentTransferCascade)

    for watcher in (
        vendor_block_watcher,
        brand_budget_watcher,
        subsidiary_capacity_watcher,
        trend_cadence_watcher,
        auto_block_rule_learner,
        kpi_history_recorder,
        story_pack_writer,
    ):
        monkeypatch.setattr(watcher, "start", lambda *args, **kwargs: None)
        monkeypatch.setattr(watcher, "stop", lambda *args, **kwargs: None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("vertical", "world_env", "expected_world"),
    [
        ("telco", None, "telco"),
        ("telco", "", "telco"),
        ("telco", "   ", "telco"),
    ],
)
async def test_lifespan_selects_expected_world_for_vertical(
    monkeypatch: pytest.MonkeyPatch,
    vertical: str,
    world_env: str | None,
    expected_world: str,
    tmp_path,
) -> None:
    from api.server.world import service as world_service_module
    from api.server.services import world_bridge as world_bridge_module

    _patch_live_lifespan_dependencies(monkeypatch)
    from api.shared.vertical_loader import build_runtime

    environment = {"ZAVA_VERTICAL": vertical}
    if world_env is not None:
        environment["ZAVA_WORLD"] = world_env
    monkeypatch.setattr(
        app_state,
        "runtime",
        build_runtime(environment, data_root=tmp_path),
        raising=False,
    )
    monkeypatch.delenv("ZAVA_VERTICAL", raising=False)
    monkeypatch.delenv("ZAVA_WORLD", raising=False)

    requested_worlds: list[str] = []
    stopped: list[str] = []

    class FakeWorldService:
        async def run(self) -> None:
            await _sleep_forever()

        def stop(self) -> None:
            stopped.append("service")

    class FakeWorldBridge:
        def __init__(self, _state) -> None:
            self.started = 0
            self.stopped = 0

        def start(self) -> None:
            self.started += 1

        def stop(self) -> None:
            self.stopped += 1

    fake_service = FakeWorldService()
    fake_bridge: FakeWorldBridge | None = None

    def fake_for_world(cls, world_name: str, *, seed: int, bus, speed: float):
        requested_worlds.append(world_name)
        return fake_service

    def fake_bridge_factory(state):
        nonlocal fake_bridge
        fake_bridge = FakeWorldBridge(state)
        return fake_bridge

    monkeypatch.setattr(world_service_module.ActorWorldService, "for_world", classmethod(fake_for_world))
    monkeypatch.setattr(world_bridge_module, "WorldBridge", fake_bridge_factory)
    set_active_player(None)

    manager = lifespan(app)
    await manager.__aenter__()
    await asyncio.sleep(0)
    try:
        assert current_player() is None
        assert requested_worlds == [expected_world]
        assert app_state.world_service is fake_service
        assert fake_bridge is not None
        assert fake_bridge.started == 1
    finally:
        await manager.__aexit__(None, None, None)

    assert stopped == ["service"]
    assert fake_bridge is not None
    assert fake_bridge.stopped == 1


@pytest.mark.asyncio
async def test_lifespan_rejects_world_owned_by_another_vertical(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from api.shared.vertical_loader import build_runtime

    with pytest.raises(
        ValueError,
        match="world 'support' is not owned by vertical 'telco'",
    ):
        build_runtime(
            {
                "ZAVA_VERTICAL": "telco",
                "ZAVA_WORLD": "support",
            },
            data_root=tmp_path,
        )


@pytest.mark.asyncio
async def test_telco_lifespan_skips_agency_watchers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from api.server.services.ambient_agents import vendor_block_watcher
    from api.shared.vertical_loader import build_runtime

    _patch_live_lifespan_dependencies(monkeypatch)
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )
    monkeypatch.setattr(
        app_state,
        "runtime",
        replace(runtime, world_name=None, world_scale_name=None),
        raising=False,
    )
    starts: list[str] = []
    monkeypatch.setattr(
        vendor_block_watcher,
        "start",
        lambda *_args, **_kwargs: starts.append("vendor"),
    )

    async with lifespan(app):
        await asyncio.sleep(0)

    assert starts == []
