from __future__ import annotations

import asyncio
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.server.main import app, lifespan
from api.server.state import AppState
from api.server.services.replay.player import current_player, set_active_player


async def _sleep_forever(*_args, **_kwargs) -> None:
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        raise


def _prepare_cadence_test_state(monkeypatch: pytest.MonkeyPatch) -> tuple[AppState, dict[str, int]]:
    from api.server import state as state_module
    from api.server.mcp_tools import query_function_fm as query_function_fm_module
    from api.server.services import cadence_loader as cadence_loader_module
    from api.server.services import ambient_dispatcher as ambient_dispatcher_module
    from api.server.services import fleet_manager_service as fleet_manager_service_module
    import api.server.mcp_tools as mcp_tools_module

    calls = {"ambient_start": 0}

    class FakeAmbientDispatcher:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def start(self) -> None:
            calls["ambient_start"] += 1

        async def aclose(self) -> None:
            return None

        async def dispatch(self, *_args, **_kwargs) -> None:
            return None

    class FakeFunctionFleetManager:
        def __init__(self, *args, **kwargs) -> None:
            return None

    monkeypatch.setattr(ambient_dispatcher_module, "AmbientDispatcher", FakeAmbientDispatcher)
    monkeypatch.setattr(cadence_loader_module, "load_cadences", lambda _path: [
        SimpleNamespace(name="cadence-test", schedule="* * * * *", fires_ambient_agent="ceo")
    ])
    monkeypatch.setattr(mcp_tools_module, "build_function_fm_tools", lambda *args, **kwargs: [])
    monkeypatch.setattr(query_function_fm_module, "make_query_function_fm_tool", lambda _state: object())
    monkeypatch.setattr(fleet_manager_service_module, "FunctionFleetManager", FakeFunctionFleetManager)
    monkeypatch.setattr(state_module, "_run_dream_pass_cadence", _sleep_forever)

    app_state = AppState()
    app_state._entity_plane_enabled = True
    app_state.entities = SimpleNamespace(close=lambda: None)
    app_state.kpi_store = object()
    app_state._dream_pass_orchestrator = object()
    app_state._run_cadence = _sleep_forever
    return app_state, calls
from api.server.services.replay.tape_format import (
    EVENTS_NAME,
    META_NAME,
    MUTATIONS_NAME,
    SNAPSHOT_DIR,
    TAPE_FORMAT_VERSION,
)


def _add_json(tf: tarfile.TarFile, name: str, payload: object) -> None:
    content = json.dumps(payload).encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    tf.addfile(info, io.BytesIO(content))


def _add_ndjson(tf: tarfile.TarFile, name: str, rows: list[dict]) -> None:
    content = b"\n".join(json.dumps(row).encode("utf-8") for row in rows) + b"\n"
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    tf.addfile(info, io.BytesIO(content))


def _build_tape(tmp_path: Path) -> Path:
    tape_path = tmp_path / "mode-wiring.tape.tar.gz"
    with tarfile.open(tape_path, "w:gz") as tf:
        _add_json(
            tf,
            f"./{META_NAME}",
            {
                "tape_id": "mode-wiring-test",
                "recorded_at": "2026-05-22T10:00:00+00:00",
                "duration_s": 1.0,
                "version": TAPE_FORMAT_VERSION,
                "app_sha": "testsha",
            },
        )
        _add_ndjson(tf, f"./{EVENTS_NAME}", [{"t": 0.0, "event": {"type": "workflow.started", "workflow_id": "wf-1"}}])
        _add_ndjson(tf, f"./{MUTATIONS_NAME}", [])
        _add_json(tf, f"./{SNAPSHOT_DIR}workflows.json", [])
        _add_json(tf, f"./{SNAPSHOT_DIR}exceptions.json", [])
        _add_json(tf, f"./{SNAPSHOT_DIR}personae.json", {"items": []})
        _add_json(tf, f"./{SNAPSHOT_DIR}functions.json", [])
        _add_json(tf, f"./{SNAPSHOT_DIR}memories.json", {"items": []})
        _add_json(tf, f"./{SNAPSHOT_DIR}lessons.json", {"items": []})
        _add_json(tf, f"./{SNAPSHOT_DIR}kpis.json", {"values": []})
        _add_json(tf, f"./{SNAPSHOT_DIR}audit_summary.json", {"total": 0, "by_action": {}})
    return tape_path


@pytest.mark.parametrize(
    ("mode_value", "expected"),
    [
        (None, False),
        ("live", False),
        ("replay", True),
        ("  REPLAY  ", True),
    ],
)
def test_is_replay_reads_env_case_insensitively(monkeypatch: pytest.MonkeyPatch, mode_value: str | None, expected: bool) -> None:
    from api.server.services.replay.mode import is_replay

    if mode_value is None:
        monkeypatch.delenv("ZAVA_MODE", raising=False)
    else:
        monkeypatch.setenv("ZAVA_MODE", mode_value)

    assert is_replay() is expected


async def test_app_state_skips_cadence_tasks_in_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTITY_PLANE_ENABLED", "0")
    monkeypatch.setenv("DREAM_PASS_DEMO_CADENCE_SECONDS", "1")
    monkeypatch.setenv("ZAVA_MODE", "replay")

    app_state, calls = _prepare_cadence_test_state(monkeypatch)
    try:
        app_state.init_function_fms()
        assert app_state._cadence_tasks == []
        assert calls["ambient_start"] == 0
    finally:
        await app_state.aclose()


async def test_app_state_starts_cadence_tasks_when_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTITY_PLANE_ENABLED", "0")
    monkeypatch.setenv("DREAM_PASS_DEMO_CADENCE_SECONDS", "1")
    monkeypatch.delenv("ZAVA_MODE", raising=False)

    app_state, calls = _prepare_cadence_test_state(monkeypatch)
    try:
        app_state.init_function_fms()
        assert app_state._cadence_tasks
        assert calls["ambient_start"] == 1
    finally:
        await app_state.aclose()


async def test_lifespan_replay_starts_player_without_simulator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from api.server import main as main_module

    tape_path = _build_tape(tmp_path)
    ramp_calls = 0

    async def fake_ramp_loop() -> None:
        nonlocal ramp_calls
        ramp_calls += 1

    monkeypatch.setenv("ZAVA_MODE", "replay")
    monkeypatch.setenv("ZAVA_TAPE_PATH", str(tape_path))
    monkeypatch.setattr(main_module.simulator_orchestrator, "ramp_loop", fake_ramp_loop)
    set_active_player(None)

    manager = lifespan(app)
    await manager.__aenter__()
    try:
        assert current_player() is not None
        assert ramp_calls == 0
    finally:
        await manager.__aexit__(None, None, None)

    assert current_player() is None


async def test_lifespan_replay_closes_loader_when_player_start_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from api.server import main as main_module
    from api.server.services.replay import player as player_module
    from api.server.services.replay import tape_loader as tape_loader_module

    tape_path = _build_tape(tmp_path)
    closed = 0
    aclosed = False
    original_close = tape_loader_module.TapeLoader.close
    original_aclose = main_module.app_state.aclose

    async def fake_start(self) -> None:
        raise RuntimeError("boom")

    def tracking_close(self) -> None:
        nonlocal closed
        closed += 1
        original_close(self)

    async def tracking_aclose() -> None:
        nonlocal aclosed
        aclosed = True
        await original_aclose()

    monkeypatch.setenv("ZAVA_MODE", "replay")
    monkeypatch.setenv("ZAVA_TAPE_PATH", str(tape_path))
    monkeypatch.setattr(player_module.Player, "start", fake_start)
    monkeypatch.setattr(tape_loader_module.TapeLoader, "close", tracking_close)
    monkeypatch.setattr(main_module.app_state, "aclose", tracking_aclose)
    set_active_player(None)

    manager = lifespan(app)
    with pytest.raises(RuntimeError, match="boom"):
        await manager.__aenter__()

    assert closed == 1
    assert aclosed is True
    assert current_player() is None


async def test_lifespan_live_mode_does_not_set_player(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.server import main as main_module
    from api.server.services.ambient_agents import (
        auto_block_rule_learner,
        brand_budget_watcher,
        kpi_history_recorder,
        story_pack_writer,
        subsidiary_capacity_watcher,
        trend_cadence_watcher,
        vendor_block_watcher,
    )
    from api.server.routes import blueprint as blueprint_module
    from api.server.eval import online_subscriber as online_subscriber_module
    from api.server.routes import whats_new as whats_new_module
    from api.server.services import portal_orchestration as portal_orchestration_module
    from api.server.services import persona_responder as persona_responder_module
    from api.server.services.ambient_agents import talent_transfer_cascade as talent_transfer_cascade_module

    calls = {"fm_start": 0, "ramp": 0}
    ramp_cancelled = asyncio.Event()

    async def fake_fm_start() -> None:
        calls["fm_start"] += 1

    async def fake_fm_stop() -> None:
        return None

    async def fake_ramp_loop() -> None:
        calls["ramp"] += 1
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            ramp_cancelled.set()
            raise

    async def fake_register(_app) -> None:
        return None

    async def fake_shutdown(_app) -> None:
        return None

    def fake_attach(*_args, **_kwargs):
        return lambda: None

    class FakeTalentTransferCascade:
        def __init__(self, *args, **kwargs) -> None:
            self.started = False

        def start(self) -> None:
            self.started = True

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

    original_aclose = main_module.app_state.aclose
    closed = False

    async def fake_aclose() -> None:
        nonlocal closed
        closed = True
        await original_aclose()

    monkeypatch.setattr(main_module.app_state, "aclose", fake_aclose)
    set_active_player(None)

    manager = lifespan(app)
    await manager.__aenter__()
    await asyncio.sleep(0)
    try:
        assert current_player() is None
        assert calls["fm_start"] == 1
        assert calls["ramp"] == 1
    finally:
        await manager.__aexit__(None, None, None)

    assert current_player() is None
    assert closed is True
    assert ramp_cancelled.is_set()
