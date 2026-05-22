from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from api.server.services.audit_logger import AuditLogger
from api.server.services.kpi_store import KpiStore
from api.server.services.memory.domain_memory import build_domain_memories
from api.server.services.memory.fallback_memory import FallbackMemory
from api.server.services.replay.mutation_bus import MutationBus, get_active_bus, set_active_bus
from api.server.services.replay.snapshot import take_snapshot
from api.server.services.replay.tape_format import META_NAME, MUTATIONS_NAME, SNAPSHOT_DIR, TAPE_FORMAT_VERSION
from api.server.services.replay.tape_loader import TapeLoader
from api.server.services.state_store import StateStore
from api.server.state import app_state
from api.shared.types import Exception_, Workflow

from api.server.services.replay.hydrate import hydrate_from_snapshot


@pytest.fixture
def isolated_app_state(tmp_path: Path):
    original_store = app_state.store
    original_audit = app_state.audit
    original_domain_memories = app_state.domain_memories
    had_kpi_store = hasattr(app_state, "kpi_store")
    original_kpi_store = getattr(app_state, "kpi_store", None)
    original_bus = get_active_bus()

    app_state.store = StateStore()
    app_state.audit = AuditLogger()
    app_state.domain_memories = build_domain_memories(
        domains=["hiring", "vendor_kyc"],
        memory=FallbackMemory(),
    )
    app_state.kpi_store = KpiStore(tmp_path / "kpis.sqlite")
    set_active_bus(None)

    try:
        yield
    finally:
        for memory_store in app_state.domain_memories.values():
            memory_store.delete_all()
        app_state.store = original_store
        app_state.audit = original_audit
        app_state.domain_memories = original_domain_memories
        if had_kpi_store:
            app_state.kpi_store = original_kpi_store
        else:
            delattr(app_state, "kpi_store")
        set_active_bus(original_bus)


def _add_json(tf: tarfile.TarFile, name: str, payload: object) -> None:
    content = json.dumps(payload).encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    tf.addfile(info, io.BytesIO(content))


def _make_loader(
    tmp_path: Path,
    *,
    snapshot_dir: Path | None = None,
    workflows: list[dict] | None = None,
    exceptions: list[dict] | None = None,
    memories: list[dict] | None = None,
    lessons: list[dict] | None = None,
) -> TapeLoader:
    if snapshot_dir is None:
        snapshot = {
            "workflows.json": workflows or [],
            "exceptions.json": exceptions or [],
            "personae.json": {"items": []},
            "functions.json": [],
            "memories.json": {"items": memories or []},
            "lessons.json": {"items": lessons or []},
            "kpis.json": {"values": []},
            "audit_summary.json": {"total": 0, "by_action": {}},
        }
    else:
        snapshot = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in snapshot_dir.glob("*.json")
        }

    tape_path = tmp_path / "hydrate.tape.tar.gz"
    with tarfile.open(tape_path, "w:gz") as tf:
        _add_json(
            tf,
            f"./{META_NAME}",
            {
                "tape_id": "hydrate-test",
                "recorded_at": "2026-05-22T10:00:00+00:00",
                "duration_s": 1.0,
                "version": TAPE_FORMAT_VERSION,
                "app_sha": "testsha",
            },
        )
        (tmp_path / "empty.ndjson").write_text("", encoding="utf-8")
        tf.add(tmp_path / "empty.ndjson", arcname=f"./{MUTATIONS_NAME}")
        for filename, payload in snapshot.items():
            _add_json(tf, f"./{SNAPSHOT_DIR}{filename}", payload)

    return TapeLoader(tape_path).load()


def test_hydrate_from_snapshot_restores_workflows_and_domain_memories(
    tmp_path: Path,
    isolated_app_state,
) -> None:
    workflow = Workflow(
        id="wf-hydrate-001",
        type="expense-claim",
        status="awaiting_hitl",
        current_phase="Audit",
        created_at=1_716_399_200.0,
        sla_due_at=1_716_485_600.0,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"amount": 1200},
        metadata={"role_id": "role-123"},
    )
    app_state.store.upsert_workflow(workflow)
    app_state.store.upsert_candidate({"id": "candidate-stale", "name": "Stale Candidate"})
    app_state.store._mcp_calls["wf-stale"] = [{"tool": "stale"}]
    app_state.domain_memories["hiring"].add(
        "Controller asked for supporting evidence.",
        agent_skill="persona:controller",
        workflow_id=workflow.id,
    )
    app_state.domain_memories["vendor_kyc"].add_distilled(
        "Vendors with repeated sanctions checks should be escalated.",
        metadata={"source": "dream-consolidation", "consolidated_at": "2026-05-22T10:00:00Z"},
    )

    snapshot_dir = tmp_path / "snapshot_t0"
    take_snapshot(snapshot_dir)

    app_state.store._workflows.clear()
    app_state.store._phases.clear()
    app_state.store._spans.clear()
    app_state.store._exceptions.clear()
    app_state.store._role_index.clear()
    for memory_store in app_state.domain_memories.values():
        memory_store.delete_all()

    loader = _make_loader(tmp_path, snapshot_dir=snapshot_dir)
    try:
        hydrate_from_snapshot(loader)
    finally:
        loader.close()

    workflows = app_state.store.list_workflows()
    assert [w.model_dump(by_alias=True, mode="json") for w in workflows] == [workflow.model_dump(by_alias=True, mode="json")]

    hiring_entries = app_state.domain_memories["hiring"].list_all()
    assert [entry["memory"] for entry in hiring_entries] == ["Controller asked for supporting evidence."]
    assert [entry["metadata"]["kind"] for entry in hiring_entries] == ["working"]
    assert hiring_entries[0]["metadata"]["workflow_id"] == workflow.id

    vendor_entries = app_state.domain_memories["vendor_kyc"].list_all()
    assert [entry["memory"] for entry in vendor_entries] == [
        "Vendors with repeated sanctions checks should be escalated.",
    ]
    assert [entry["metadata"]["kind"] for entry in vendor_entries] == ["lesson"]
    assert app_state.store.list_candidates() == []
    assert app_state.store.get_mcp_calls("wf-stale") == []


def test_hydrate_from_snapshot_restores_exceptions(tmp_path: Path, isolated_app_state) -> None:
    workflow = Workflow(
        id="wf-hydrate-exc",
        type="expense-claim",
        status="in_progress",
        current_phase="Audit",
        created_at=1_716_399_200.0,
        sla_due_at=1_716_485_600.0,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"amount": 900},
    )
    exception = Exception_(
        id="exc-hydrate-001",
        workflow_id=workflow.id,
        composed_by="deterministic",
        severity="high",
        category="threshold-exceeded",
        summary="Needs controller review.",
        recommendation="Escalate for approval.",
        created_at=1_716_399_260.0,
    )

    loader = _make_loader(
        tmp_path,
        workflows=[workflow.model_dump(by_alias=True, mode="json")],
        exceptions=[exception.model_dump(by_alias=True, mode="json")],
    )
    try:
        hydrate_from_snapshot(loader)
    finally:
        loader.close()

    exceptions = app_state.store.list_exceptions(include_resolved=True)
    assert [e.model_dump(by_alias=True, mode="json") for e in exceptions] == [exception.model_dump(by_alias=True, mode="json")]
    assert app_state.store.get_workflow(workflow.id).active_exception_id == exception.id


def test_hydrate_from_snapshot_does_not_reemit_on_active_bus(tmp_path: Path, isolated_app_state) -> None:
    workflow = Workflow(
        id="wf-hydrate-bus",
        type="expense-claim",
        status="in_progress",
        current_phase="Audit",
        created_at=1_716_399_200.0,
        sla_due_at=1_716_485_600.0,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"amount": 500},
    )
    loader = _make_loader(
        tmp_path,
        workflows=[workflow.model_dump(by_alias=True, mode="json")],
        memories=[
            {
                "id": "mem-1",
                "domain": "hiring",
                "memory": "Hydrated working note.",
                "agent_skill": "persona:controller",
                "workflow_id": workflow.id,
                "captured_at": "2026-05-22T10:00:00Z",
                "metadata": {
                    "domain": "hiring",
                    "kind": "working",
                    "agent_skill": "persona:controller",
                    "workflow_id": workflow.id,
                    "captured_at": "2026-05-22T10:00:00Z",
                },
            }
        ],
    )
    bus = MutationBus()
    set_active_bus(bus)

    try:
        hydrate_from_snapshot(loader)
    finally:
        loader.close()

    assert bus.entries == []
    assert get_active_bus() is bus


def test_hydrate_from_snapshot_restores_bus_after_failure(
    tmp_path: Path,
    isolated_app_state,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = Workflow(
        id="wf-hydrate-fail",
        type="expense-claim",
        status="in_progress",
        current_phase="Audit",
        created_at=1_716_399_200.0,
        sla_due_at=1_716_485_600.0,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"amount": 500},
    )
    loader = _make_loader(
        tmp_path,
        workflows=[workflow.model_dump(by_alias=True, mode="json")],
    )
    bus = MutationBus()
    set_active_bus(bus)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("api.server.services.replay.hydrate._hydrate_workflows", _boom)

    try:
        with pytest.raises(RuntimeError, match="boom"):
            hydrate_from_snapshot(loader)
    finally:
        loader.close()

    assert get_active_bus() is bus
