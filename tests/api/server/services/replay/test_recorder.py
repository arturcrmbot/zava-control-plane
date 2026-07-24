"""Tests for the Recorder service."""
from __future__ import annotations

import asyncio
import json
import tarfile
from pathlib import Path

import pytest

from api.server.services.replay.mutation_bus import MutationBus, get_active_bus, set_active_bus
from api.server.services.replay.tape_format import TAPE_FORMAT_VERSION
from api.server.services.state_store import StateStore
from api.server.state import app_state
from api.shared.events import FleetEvent
from api.shared.types import Workflow


@pytest.fixture
def isolated_app_state():
    """Isolate app_state.store and app_state.bus for recorder tests.

    Restores originals and clears mutation bus in teardown.
    """
    from api.server.services.event_bus import EventBus

    original_store = app_state.store
    original_bus = app_state.bus

    app_state.store = StateStore()
    app_state.bus = EventBus()

    try:
        yield
    finally:
        set_active_bus(None)
        app_state.store = original_store
        app_state.bus = original_bus


async def test_smoke_recorder_creates_valid_tarball(tmp_path: Path, isolated_app_state):
    """Smoke: start, emit 2 events, stop — verify tarball structure and content."""
    from api.server.services.replay.recorder import Recorder

    out_path = tmp_path / "tape.tar.gz"
    recorder = Recorder(out_path=out_path, flush_interval_s=300.0)

    await recorder.start()

    app_state.bus.emit(FleetEvent(type="fleet.tick", workflow_id="wf-001"))
    await asyncio.sleep(0.01)
    app_state.bus.emit(FleetEvent(type="workflow.started", workflow_id="wf-002"))

    result = await recorder.stop()

    assert result == out_path
    assert out_path.exists()

    with tarfile.open(out_path, "r:gz") as tf:
        names = tf.getnames()

    assert "./meta.json" in names
    assert "./events.ndjson" in names
    assert "./mutations.ndjson" in names

    snapshot_files = [n for n in names if n.startswith("./snapshot_t0/")]
    assert len(snapshot_files) > 0

    with tarfile.open(out_path, "r:gz") as tf:
        events_data = tf.extractfile("./events.ndjson").read().decode()  # type: ignore[union-attr]

    lines = [line for line in events_data.strip().splitlines() if line]
    assert len(lines) == 2

    records = [json.loads(line) for line in lines]
    assert records[0]["t"] <= records[1]["t"]
    assert records[0]["event"]["type"] == "fleet.tick"
    assert records[1]["event"]["type"] == "workflow.started"


async def test_mutation_capture(tmp_path: Path, isolated_app_state):
    """Mutations from upsert_workflow land in mutations.ndjson with kind=='workflow'."""
    from api.server.services.replay.recorder import Recorder

    out_path = tmp_path / "tape.tar.gz"
    recorder = Recorder(out_path=out_path, flush_interval_s=300.0)

    await recorder.start()

    wf = Workflow(
        id="wf-rec-001",
        type="expense-claim",
        status="awaiting_hitl",
        current_phase="Audit",
        created_at=1_716_399_200.0,
        sla_due_at=1_716_485_600.0,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"amount": 500},
    )
    app_state.store.upsert_workflow(wf)

    # Emit an event to trigger the drain so the mutation gets timestamped.
    app_state.bus.emit(FleetEvent(type="fleet.tick"))

    await recorder.stop()

    with tarfile.open(out_path, "r:gz") as tf:
        mut_data = tf.extractfile("./mutations.ndjson").read().decode()  # type: ignore[union-attr]

    lines = [line for line in mut_data.strip().splitlines() if line]
    assert len(lines) >= 1

    records = [json.loads(line) for line in lines]
    assert any(r["kind"] == "workflow" for r in records)


async def test_tool_completion_mutation_is_taped_with_triggering_event(
    tmp_path: Path,
    isolated_app_state,
):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from api.server.services.replay.recorder import Recorder
    from api.server.services.workflow_event_ingestor import WorkflowEventIngestor

    workflow_id = "wf-tool-association"
    app_state.store.upsert_workflow(Workflow(
        id=workflow_id,
        type="vendor-kyc",
        status="in_progress",
        current_phase="KYC Diligence",
        created_at=1_716_399_200.0,
        sla_due_at=1_716_485_600.0,
        jurisdiction="London-Zava",
        agency="Zava",
    ))
    ingestor = WorkflowEventIngestor(SimpleNamespace(
        bus=app_state.bus,
        store=app_state.store,
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
        domain_memories={},
        cost_budget=MagicMock(),
    ))
    out_path = tmp_path / "tool-association.tar.gz"
    recorder = Recorder(out_path=out_path, flush_interval_s=300.0)

    await recorder.start()
    try:
        await ingestor.ingest(
            workflow_id,
            "instance-tool-association",
            "tool.invoked",
            {
                "tool": "vendor_registry_lookup",
                "stage": "complete",
                "tool_call_id": "call-tape-1",
                "args": '{"vendorId":"V-1"}',
                "result": '{"status":"active"}',
                "success": True,
                "duration_ms": 7,
            },
            at=1_716_399_201.0,
        )
        await asyncio.sleep(0.05)
        app_state.bus.emit(FleetEvent(
            type="fleet.tick",
            workflow_id=workflow_id,
        ))
    finally:
        await recorder.stop()

    with tarfile.open(out_path, "r:gz") as tf:
        events = [
            json.loads(line)
            for line in tf.extractfile("./events.ndjson").read().decode().splitlines()  # type: ignore[union-attr]
        ]
        mutations = [
            json.loads(line)
            for line in tf.extractfile("./mutations.ndjson").read().decode().splitlines()  # type: ignore[union-attr]
        ]

    tool_event = next(
        record
        for record in events
        if record["event"]["type"] == "durable.executor.invoked"
    )
    marker_event = next(
        record for record in events if record["event"]["type"] == "fleet.tick"
    )
    tool_mutation = next(
        record
        for record in mutations
        if record["kind"] == "mcp_call"
        and record["patch"]["toolCallId"] == "call-tape-1"
    )
    assert tool_event["t"] <= tool_mutation["t"] < marker_event["t"]
    assert tool_mutation["t"] == pytest.approx(tool_event["t"], abs=0.01)


async def test_meta_json_shape(tmp_path: Path, isolated_app_state):
    """meta.json contains all required fields with correct types and values."""
    from api.server.services.replay.recorder import Recorder

    out_path = tmp_path / "tape.tar.gz"
    recorder = Recorder(out_path=out_path, app_sha="abc123", flush_interval_s=300.0)

    await recorder.start()
    await recorder.stop()

    with tarfile.open(out_path, "r:gz") as tf:
        meta = json.loads(tf.extractfile("./meta.json").read())  # type: ignore[union-attr]

    assert meta["tape_id"].startswith("tape_")
    assert len(meta["tape_id"]) == len("tape_") + 8
    assert meta["recorded_at"]
    assert meta["duration_s"] > 0
    assert meta["version"] == TAPE_FORMAT_VERSION
    assert meta["app_sha"] == "abc123"


async def test_no_events_after_stop(tmp_path: Path, isolated_app_state):
    """Events emitted after stop() must not appear in the tape."""
    from api.server.services.replay.recorder import Recorder

    out_path = tmp_path / "tape.tar.gz"
    recorder = Recorder(out_path=out_path, flush_interval_s=300.0)

    await recorder.start()
    app_state.bus.emit(FleetEvent(type="fleet.tick", workflow_id="wf-before"))
    await recorder.stop()

    # Emit after stop — recorder should be unsubscribed and ignore this.
    app_state.bus.emit(FleetEvent(type="workflow.started", workflow_id="wf-after"))

    with tarfile.open(out_path, "r:gz") as tf:
        events_data = tf.extractfile("./events.ndjson").read().decode()  # type: ignore[union-attr]

    lines = [line for line in events_data.strip().splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["event"]["workflow_id"] == "wf-before"


async def test_periodic_flush_captures_mutation_without_followup_event(tmp_path: Path, isolated_app_state):
    from api.server.services.replay.recorder import Recorder

    out_path = tmp_path / "tape.tar.gz"
    recorder = Recorder(out_path=out_path, flush_interval_s=0.01)

    await recorder.start()

    app_state.store.upsert_workflow(
        Workflow(
            id="wf-flush-001",
            type="expense-claim",
            status="awaiting_hitl",
            current_phase="Audit",
            created_at=1_716_399_200.0,
            sla_due_at=1_716_485_600.0,
            jurisdiction="London-Zava",
            agency="Zava",
            payload={"amount": 500},
        )
    )
    await asyncio.sleep(0.05)
    await recorder.stop()

    with tarfile.open(out_path, "r:gz") as tf:
        mut_data = tf.extractfile("./mutations.ndjson").read().decode()  # type: ignore[union-attr]

    records = [json.loads(line) for line in mut_data.splitlines() if line]
    assert any(record["kind"] == "workflow" and record["t"] >= 0 for record in records)


async def test_stop_preserves_replaced_active_bus(tmp_path: Path, isolated_app_state):
    from api.server.services.replay.recorder import Recorder

    out_path = tmp_path / "tape.tar.gz"
    recorder = Recorder(out_path=out_path, flush_interval_s=300.0)

    await recorder.start()
    replacement_bus = MutationBus()
    set_active_bus(replacement_bus)

    await recorder.stop()

    assert get_active_bus() is replacement_bus


async def test_start_failure_cleans_up_global_state(tmp_path: Path, isolated_app_state, monkeypatch: pytest.MonkeyPatch):
    from api.server.services.replay.recorder import Recorder

    out_path = tmp_path / "tape.tar.gz"
    recorder = Recorder(out_path=out_path, flush_interval_s=300.0)

    def _boom(coro, *args, **kwargs):
        coro.close()
        raise RuntimeError("boom")

    monkeypatch.setattr(asyncio, "create_task", _boom)

    with pytest.raises(RuntimeError, match="boom"):
        await recorder.start()

    assert get_active_bus() is None
    assert app_state.bus._any == []
    assert list(tmp_path.glob(".recorder-*")) == []


async def test_stop_failure_still_cleans_up_owned_work_dir(tmp_path: Path, isolated_app_state, monkeypatch: pytest.MonkeyPatch):
    from api.server.services.replay.recorder import Recorder

    out_path = tmp_path / "tape.tar.gz"
    recorder = Recorder(out_path=out_path, flush_interval_s=300.0)

    await recorder.start()

    class _BrokenTar:
        def __enter__(self):
            raise OSError("disk full")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(tarfile, "open", lambda *args, **kwargs: _BrokenTar())

    with pytest.raises(OSError, match="disk full"):
        await recorder.stop()

    assert list(tmp_path.glob(".recorder-*")) == []


async def test_periodic_flush_retry_does_not_duplicate_events(tmp_path: Path, isolated_app_state, monkeypatch: pytest.MonkeyPatch):
    from api.server.services.replay.recorder import Recorder

    out_path = tmp_path / "tape.tar.gz"
    recorder = Recorder(out_path=out_path, flush_interval_s=0.01)

    original_open = Path.open
    mutation_open_failures = {"remaining": 1}

    def flaky_open(path: Path, *args, **kwargs):
        if (
            path.name == "mutations.ndjson"
            and args
            and args[0] == "a"
            and mutation_open_failures["remaining"]
        ):
            mutation_open_failures["remaining"] -= 1
            raise OSError("mutation append failed")
        return original_open(path, *args, **kwargs)

    await recorder.start()
    monkeypatch.setattr(Path, "open", flaky_open)

    app_state.bus.emit(FleetEvent(type="fleet.tick", workflow_id="wf-dup-check"))
    app_state.store.upsert_workflow(
        Workflow(
            id="wf-dup-check",
            type="expense-claim",
            status="awaiting_hitl",
            current_phase="Audit",
            created_at=1_716_399_200.0,
            sla_due_at=1_716_485_600.0,
            jurisdiction="London-Zava",
            agency="Zava",
            payload={"amount": 500},
        )
    )
    await asyncio.sleep(0.05)
    await recorder.stop()

    with tarfile.open(out_path, "r:gz") as tf:
        events_data = tf.extractfile("./events.ndjson").read().decode()  # type: ignore[union-attr]

    records = [json.loads(line) for line in events_data.splitlines() if line]
    assert [record["event"]["workflow_id"] for record in records] == ["wf-dup-check"]


async def test_periodic_flush_survives_drain_error(tmp_path: Path, isolated_app_state, monkeypatch: pytest.MonkeyPatch):
    from api.server.services.replay.recorder import Recorder

    out_path = tmp_path / "tape.tar.gz"
    recorder = Recorder(out_path=out_path, flush_interval_s=0.01)

    await recorder.start()

    original_drain = recorder._drain_mutations
    failures = {"remaining": 1}

    def flaky_drain() -> None:
        if failures["remaining"]:
            failures["remaining"] -= 1
            raise RuntimeError("drain failed")
        original_drain()

    monkeypatch.setattr(recorder, "_drain_mutations", flaky_drain)

    app_state.store.upsert_workflow(
        Workflow(
            id="wf-drain-retry",
            type="expense-claim",
            status="awaiting_hitl",
            current_phase="Audit",
            created_at=1_716_399_200.0,
            sla_due_at=1_716_485_600.0,
            jurisdiction="London-Zava",
            agency="Zava",
            payload={"amount": 500},
        )
    )
    await asyncio.sleep(0.05)
    await recorder.stop()

    with tarfile.open(out_path, "r:gz") as tf:
        mut_data = tf.extractfile("./mutations.ndjson").read().decode()  # type: ignore[union-attr]

    records = [json.loads(line) for line in mut_data.splitlines() if line]
    assert any(record["id"] == "wf-drain-retry" for record in records)
