from __future__ import annotations

import asyncio
import io
import json
import os
import tarfile
import time
from pathlib import Path

import pytest

os.environ.setdefault("ENTITY_PLANE_ENABLED", "0")

from api.server.services.event_bus import EventBus
from api.server.services.memory.domain_memory import build_domain_memories
from api.server.services.memory.fallback_memory import FallbackMemory
from api.server.services.replay.mutation_bus import get_active_bus, set_active_bus
from api.server.services.replay.tape_format import (
    EVENTS_NAME,
    META_NAME,
    MUTATIONS_NAME,
    SNAPSHOT_DIR,
    TAPE_FORMAT_VERSION,
)
from api.server.services.replay.tape_loader import TapeLoader
from api.server.services.state_store import StateStore
from api.server.state import app_state
from api.shared.types import Workflow


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, secs: float) -> None:
        self.now += secs
        await asyncio.sleep(0)


@pytest.fixture
def isolated_app_state() -> None:
    original_store = app_state.store
    original_bus = app_state.bus
    original_domain_memories = app_state.domain_memories
    original_mutation_bus = get_active_bus()

    app_state.store = StateStore()
    app_state.bus = EventBus()
    app_state.domain_memories = build_domain_memories(
        domains=["hiring"],
        memory=FallbackMemory(),
    )
    set_active_bus(None)

    try:
        yield
    finally:
        for memory_store in app_state.domain_memories.values():
            memory_store.delete_all()
        set_active_bus(original_mutation_bus)
        app_state.store = original_store
        app_state.bus = original_bus
        app_state.domain_memories = original_domain_memories


@pytest.fixture
def collected_events() -> list:
    events = []
    off = app_state.bus.on_any(lambda event: events.append(event))
    try:
        yield events
    finally:
        off()


def _workflow(workflow_id: str = "wf-replay-001") -> Workflow:
    return Workflow(
        id=workflow_id,
        type="expense-claim",
        status="in_progress",
        current_phase="Audit",
        created_at=1_716_399_200.0,
        sla_due_at=1_716_485_600.0,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"amount": 500},
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


def _build_tape(
    tmp_path: Path,
    *,
    duration_s: float,
    events: list[dict] | None = None,
    mutations: list[dict] | None = None,
    snapshot_workflows: list[dict] | None = None,
    snapshot_exceptions: list[dict] | None = None,
) -> TapeLoader:
    tape_path = tmp_path / "player.tape.tar.gz"
    with tarfile.open(tape_path, "w:gz") as tf:
        _add_json(
            tf,
            f"./{META_NAME}",
            {
                "tape_id": "player-test",
                "recorded_at": "2026-05-22T10:00:00+00:00",
                "duration_s": duration_s,
                "version": TAPE_FORMAT_VERSION,
                "app_sha": "testsha",
            },
        )
        _add_ndjson(tf, f"./{EVENTS_NAME}", events or [])
        _add_ndjson(tf, f"./{MUTATIONS_NAME}", mutations or [])
        _add_json(tf, f"./{SNAPSHOT_DIR}workflows.json", snapshot_workflows or [])
        _add_json(tf, f"./{SNAPSHOT_DIR}exceptions.json", snapshot_exceptions or [])
        _add_json(tf, f"./{SNAPSHOT_DIR}personae.json", {"items": []})
        _add_json(tf, f"./{SNAPSHOT_DIR}functions.json", [])
        _add_json(tf, f"./{SNAPSHOT_DIR}memories.json", {"items": []})
        _add_json(tf, f"./{SNAPSHOT_DIR}lessons.json", {"items": []})
        _add_json(tf, f"./{SNAPSHOT_DIR}kpis.json", {"values": []})
        _add_json(tf, f"./{SNAPSHOT_DIR}audit_summary.json", {"total": 0, "by_action": {}})
    return TapeLoader(tape_path).load()


async def _wait_until(predicate, *, attempts: int = 50) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition was not met in time")


async def test_player_emits_events_in_order_with_expected_timing(
    tmp_path: Path,
    isolated_app_state,
) -> None:
    from api.server.services.replay.player import Player

    loader = _build_tape(
        tmp_path,
        duration_s=4.0,
        events=[
            {"t": 1.0, "event": {"type": "workflow.started", "workflow_id": "wf-1"}},
            {"t": 3.0, "event": {"type": "workflow.phase.completed", "workflow_id": "wf-1"}},
        ],
    )
    clock = FakeClock()
    received: list[tuple[str, float]] = []
    two_seen = asyncio.Event()

    def collector(event) -> None:
        received.append((event.type, clock.now))
        if len(received) >= 2:
            two_seen.set()

    off = app_state.bus.on_any(collector)
    try:
        player = Player(loader, sleep_fn=clock.sleep, clock_fn=clock)
        await player.start()
        await asyncio.wait_for(two_seen.wait(), timeout=1.0)
        await player.stop()
    finally:
        off()
        loader.close()

    assert [event_type for event_type, _ in received[:2]] == [
        "workflow.started",
        "workflow.phase.completed",
    ]
    assert [seen_at for _, seen_at in received[:2]] == pytest.approx([1.0, 3.0])
    assert player.current_t() == pytest.approx(3.0)


async def test_player_loops_after_restart_pending(
    tmp_path: Path,
    isolated_app_state,
) -> None:
    from api.server.services.replay.player import Player

    loader = _build_tape(
        tmp_path,
        duration_s=4.0,
        events=[
            {"t": 1.0, "event": {"type": "workflow.started", "workflow_id": "wf-1"}},
            {"t": 3.0, "event": {"type": "workflow.phase.completed", "workflow_id": "wf-1"}},
        ],
    )
    clock = FakeClock()
    received: list[str] = []
    six_seen = asyncio.Event()

    def collector(event) -> None:
        received.append(event.type)
        if len(received) >= 6:
            six_seen.set()

    off = app_state.bus.on_any(collector)
    try:
        player = Player(
            loader,
            restart_pause_s=0.5,
            sleep_fn=clock.sleep,
            clock_fn=clock,
        )
        await player.start()
        await asyncio.wait_for(six_seen.wait(), timeout=1.0)
        await player.stop()
    finally:
        off()
        loader.close()

    assert received[:6] == [
        "workflow.started",
        "workflow.phase.completed",
        "playback.restart.pending",
        "workflow.started",
        "workflow.phase.completed",
        "playback.restart.pending",
    ]


async def test_player_stop_during_sleep_returns_promptly(
    tmp_path: Path,
    isolated_app_state,
) -> None:
    from api.server.services.replay.player import Player

    loader = _build_tape(
        tmp_path,
        duration_s=100.0,
        events=[
            {"t": 100.0, "event": {"type": "workflow.started", "workflow_id": "wf-stop"}},
        ],
    )
    player = Player(loader)
    started_at = time.monotonic()

    try:
        await player.start()
        await player.stop()
    finally:
        loader.close()

    assert time.monotonic() - started_at < 1.0


async def test_player_applies_workflow_mutation_before_later_event(
    tmp_path: Path,
    isolated_app_state,
) -> None:
    from api.server.services.replay.player import Player

    workflow = _workflow("wf-mutated")
    loader = _build_tape(
        tmp_path,
        duration_s=3.0,
        events=[
            {"t": 2.0, "event": {"type": "workflow.started", "workflow_id": workflow.id}},
        ],
        mutations=[
            {
                "t": 1.0,
                "op": "upsert",
                "kind": "workflow",
                "id": workflow.id,
                "patch": workflow.model_dump(by_alias=True, mode="json"),
            },
        ],
    )
    clock = FakeClock()
    player = Player(loader, sleep_fn=clock.sleep, clock_fn=clock)

    try:
        await player.start()
        await _wait_until(lambda: app_state.store.get_workflow(workflow.id) is not None)
        assert app_state.store.get_workflow(workflow.id).id == workflow.id
        assert player.current_t() == pytest.approx(1.0)
        await player.stop()
    finally:
        loader.close()


async def test_player_can_restart_after_stop(
    tmp_path: Path,
    isolated_app_state,
    collected_events,
) -> None:
    from api.server.services.replay.player import Player

    loader = _build_tape(
        tmp_path,
        duration_s=2.0,
        events=[
            {"t": 1.0, "event": {"type": "workflow.started", "workflow_id": "wf-restart"}},
        ],
    )
    clock = FakeClock()
    player = Player(loader, sleep_fn=clock.sleep, clock_fn=clock)

    try:
        await player.start()
        await _wait_until(
            lambda: len([event for event in collected_events if event.type == "workflow.started"]) == 1
        )
        await player.stop()

        await player.start()
        await _wait_until(
            lambda: len([event for event in collected_events if event.type == "workflow.started"]) == 2
        )
        await player.stop()
    finally:
        loader.close()

    assert [event.type for event in collected_events if event.type == "workflow.started"] == [
        "workflow.started",
        "workflow.started",
    ]


async def test_player_skips_unknown_mutation_kind_and_continues(
    tmp_path: Path,
    isolated_app_state,
    collected_events,
) -> None:
    from api.server.services.replay.player import Player

    loader = _build_tape(
        tmp_path,
        duration_s=2.0,
        events=[
            {"t": 1.0, "event": {"type": "workflow.started", "workflow_id": "wf-unknown"}},
        ],
        mutations=[
            {
                "t": 0.5,
                "op": "upsert",
                "kind": "memory",
                "id": "mem-1",
                "patch": {"domain": "hiring", "memory": "ignored"},
            },
        ],
    )
    clock = FakeClock()
    player = Player(loader, sleep_fn=clock.sleep, clock_fn=clock)

    try:
        await player.start()
        await _wait_until(lambda: any(event.type == "workflow.started" for event in collected_events))
        await player.stop()
    finally:
        loader.close()

    assert [event.type for event in collected_events][:1] == ["workflow.started"]
    assert any(event.type == "workflow.started" for event in collected_events)
