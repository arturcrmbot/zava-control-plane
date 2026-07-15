"""Tests that producers emit the event types the cosmic lens consumes."""
from unittest.mock import MagicMock

import pytest


def _capture_bus_emits():
    """Returns (bus_mock, captured_events). bus_mock.emit appends to list."""
    bus = MagicMock()
    captured: list = []
    bus.emit.side_effect = lambda ev: captured.append(ev)
    return bus, captured


def test_ambient_dispatcher_emits_ambient_decided_on_bus(monkeypatch):
    from api.server.services import ambient_dispatcher as mod

    bus, captured = _capture_bus_emits()
    audit = MagicMock()
    graph = MagicMock()
    spawn_workflow = MagicMock()
    disp = mod.AmbientDispatcher(
        bus=bus, graph=graph, audit=audit, spawn_workflow=spawn_workflow,
    )
    agent = MagicMock()
    agent.name = "test-agent"
    agent.function = "finance"
    # Method is named `_audit_decided` in this codebase (plan referred to it
    # as `_record_decision` — see commit body).
    disp._audit_decided(
        agent,
        "bus",
        {"x": 1},
        spawn_outcome={"workflow_id": "TEST-001"},
    )
    types = [e.type for e in captured]
    assert "ambient.decided" in types, (
        f"expected ambient.decided emitted on bus, saw {types}"
    )


def test_entity_graph_get_emits_entity_read(tmp_path):
    """get() should fire entity.read on the bus when called for a known id."""
    pytest.importorskip("kuzu")
    from api.server.services.entity_graph import EntityGraph, EntityWrite

    db = tmp_path / "kuzu.db"
    bus, captured = _capture_bus_emits()
    with EntityGraph(db_path=str(db)) as graph:
        graph.attach(bus=bus)
        # Plan said kind="Vendor"; actual schema uses Organisation (with
        # an attrs.kind="vendor" sub-discriminator). Adjusted to match.
        graph.upsert(EntityWrite(id="VEN-001", kind="Organisation", attrs={}))
        captured.clear()
        graph.get("VEN-001")
    types = [e.type for e in captured]
    assert "entity.read" in types, (
        f"expected entity.read emitted on get(), saw {types}"
    )


async def test_workflow_rejected_path_emits_workflow_failed():
    """The durable-event `workflow.rejected` branch should emit workflow.failed.

    Ingestion moved out of the HTTP route into the non-HTTP
    :class:`WorkflowEventIngestor` service (Phase 2); this now exercises the
    branch directly against a fresh ingestor bound to a minimal fake app_state.
    """
    import time as _time
    from types import SimpleNamespace

    from api.server.services.state_store import StateStore
    from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
    from api.shared.types import Workflow

    bus, captured = _capture_bus_emits()
    store = StateStore()
    now = _time.time()
    store.upsert_workflow(Workflow(
        id="WF-REJ", type="expense-claim", status="awaiting_hitl",
        current_phase="Triage", created_at=now, sla_due_at=now + 86400,
        jurisdiction="UK-Zava", agency="Zava",
    ))
    app_state = SimpleNamespace(
        bus=bus, store=store, audit=MagicMock(), hub=MagicMock(),
        orchestration_history={},
    )
    ingestor = WorkflowEventIngestor(app_state)

    await ingestor.ingest("WF-REJ", None, "workflow.rejected",
                          {"by": "operator", "reason": "test"})

    types = [e.type for e in captured]
    assert "workflow.failed" in types, f"expected workflow.failed, saw {types}"
    assert store.get_workflow("WF-REJ").status == "failed"


def test_observatory_event_cap_drops_excess(monkeypatch):
    """A token-bucket cap drops events past MAX_OBSERVATORY_EVENTS_PER_SEC."""
    monkeypatch.setenv("MAX_OBSERVATORY_EVENTS_PER_SEC", "5")
    # Re-import to pick up the env override (the cap is read at module load).
    import importlib
    from api.server.routes import blueprint
    importlib.reload(blueprint)

    bucket = blueprint._make_event_cap()
    # Burst 20 events instantly; only 5 should fit in the first second.
    accepted = sum(1 for _ in range(20) if bucket.allow())
    assert accepted == 5
