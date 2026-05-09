"""Dispatch tests for :class:`EntityReflector` (TASK-011).

Covers the happy-path bus → projection → graph wiring:

* ``test_reflector_dispatches_entity_write_to_upsert`` — a fake projection
  returns one :class:`EntityWrite`; the reflector calls
  :meth:`EntityGraph.upsert` and the node is readable via :meth:`get`.
* ``test_reflector_dispatches_rel_write_to_link`` — a fake projection
  emits two ``EntityWrite``s + one ``RelWrite``; the rel lands.
* ``test_reflector_silently_skips_unknown_workflow_type`` — for an
  unregistered ``workflow.type`` the reflector is a no-op (no exception,
  no graph writes, no audit). Locks part of the TASK-014 contract.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite, RelWrite
from api.server.services.entity_projections import PROJECTIONS
from api.server.services.entity_reflector import EntityReflector
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.shared.events import FleetEvent
from api.shared.types import Workflow


def _make_workflow(workflow_id: str, workflow_type: str) -> Workflow:
    now = time.time()
    return Workflow(
        id=workflow_id,
        type=workflow_type,
        current_phase="Intake",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-Test",
    )


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def store() -> StateStore:
    return StateStore()


@pytest.fixture
def reflector(bus: EventBus, store: StateStore, graph: EntityGraph):
    r = EntityReflector(bus, store, graph)
    r.start()
    try:
        yield r
    finally:
        r.aclose()


def test_reflector_dispatches_entity_write_to_upsert(
    bus: EventBus,
    store: StateStore,
    graph: EntityGraph,
    reflector: EntityReflector,
) -> None:
    """A projection that returns one EntityWrite lands one node in the graph."""

    def fake_projection(_wf: Workflow) -> list:
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-T1",
                attrs={"name": "Test", "email": "test@example.com"},
                source_workflows=("WF-1",),
            )
        ]

    PROJECTIONS["test-domain"] = fake_projection
    try:
        store.upsert_workflow(_make_workflow("WF-1", "test-domain"))
        bus.emit(FleetEvent(type="workflow.completed", workflow_id="WF-1"))

        node = graph.get("PERSON-T1")
        assert node is not None
        assert node["name"] == "Test"
        assert node["email"] == "test@example.com"
    finally:
        del PROJECTIONS["test-domain"]


def test_reflector_dispatches_rel_write_to_link(
    bus: EventBus,
    store: StateStore,
    graph: EntityGraph,
    reflector: EntityReflector,
) -> None:
    """A projection emitting two endpoints + one RelWrite lands the rel."""

    def fake_projection(_wf: Workflow) -> list:
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-T2",
                attrs={"name": "Alice"},
                source_workflows=("WF-2",),
            ),
            EntityWrite(
                kind="Organisation",
                id="ORG-T2",
                attrs={"name": "Acme"},
                source_workflows=("WF-2",),
            ),
            RelWrite(
                src_id="PERSON-T2",
                rel="EMPLOYED_BY",
                dst_id="ORG-T2",
                attrs={"role": "engineer"},
            ),
        ]

    PROJECTIONS["test-rel-domain"] = fake_projection
    try:
        store.upsert_workflow(_make_workflow("WF-2", "test-rel-domain"))
        bus.emit(FleetEvent(type="workflow.completed", workflow_id="WF-2"))

        # Verify both nodes landed.
        assert graph.get("PERSON-T2") is not None
        assert graph.get("ORG-T2") is not None

        # Verify the rel landed via the linked() helper.
        neighbours = graph.linked("PERSON-T2", rel="EMPLOYED_BY")
        assert any(n["node"]["id"] == "ORG-T2" for n in neighbours), (
            f"expected EMPLOYED_BY edge to ORG-T2, got {neighbours!r}"
        )
    finally:
        del PROJECTIONS["test-rel-domain"]


def test_reflector_silently_skips_unknown_workflow_type(
    bus: EventBus,
    store: StateStore,
    graph: EntityGraph,
    reflector: EntityReflector,
) -> None:
    """Unregistered workflow_type is a silent no-op (CON-001 / TASK-014)."""
    assert "not-registered" not in PROJECTIONS

    store.upsert_workflow(_make_workflow("WF-3", "not-registered"))

    audit_calls: list[tuple[str, dict]] = []

    class _RecordingAudit:
        def log(self, action: str, details: dict) -> None:
            audit_calls.append((action, details))

    # Re-wire the reflector with an audit recorder so we can assert silence.
    reflector.aclose()
    reflector_with_audit = EntityReflector(
        bus, store, graph, audit=_RecordingAudit()
    )
    reflector_with_audit.start()
    try:
        # Should not raise.
        bus.emit(FleetEvent(type="workflow.completed", workflow_id="WF-3"))

        # No graph writes.
        assert graph.get("PERSON-WF-3") is None
        # No audit emissions from the reflector.
        reflector_actions = [a for a, _ in audit_calls]
        assert reflector_actions == [], (
            f"expected zero audit emissions, got {reflector_actions!r}"
        )
    finally:
        reflector_with_audit.aclose()


def test_reflector_isolates_per_op_failures(
    bus: EventBus,
    store: StateStore,
    graph: EntityGraph,
) -> None:
    """A single failing op must not poison sibling ops in the same projection.

    Locks the per-op isolation contract added in Phase 1 hardening: the
    reflector wraps every dispatch in its own try/except + audit
    (``entity.write.failed``) and continues the loop instead of aborting.
    """

    def fake_projection(_wf: Workflow) -> list:
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-OK1",
                attrs={"name": "Good One"},
                source_workflows=("WF-ISO",),
            ),
            # This op will fail at upsert time: ``not_a_real_column`` is
            # not in the Person node-table schema, so Kuzu's Binder rejects
            # it. Per the contract, the loop must still dispatch the next
            # op — which is why PERSON-OK2 below has to land.
            EntityWrite(
                kind="Person",
                id="PERSON-BAD",
                attrs={"name": "Bad One", "not_a_real_column": "boom"},
                source_workflows=("WF-ISO",),
            ),
            EntityWrite(
                kind="Person",
                id="PERSON-OK2",
                attrs={"name": "Good Two"},
                source_workflows=("WF-ISO",),
            ),
        ]

    audit_calls: list[tuple[str, dict]] = []

    class _RecordingAudit:
        def log(self, action: str, details: dict) -> None:
            audit_calls.append((action, details))

    PROJECTIONS["test-isolation-domain"] = fake_projection
    reflector_iso = EntityReflector(bus, store, graph, audit=_RecordingAudit())
    reflector_iso.start()
    try:
        store.upsert_workflow(_make_workflow("WF-ISO", "test-isolation-domain"))
        # Should not raise even though one op fails.
        bus.emit(FleetEvent(type="workflow.completed", workflow_id="WF-ISO"))

        # Both good ops must have landed.
        assert graph.get("PERSON-OK1") is not None, (
            "first good op must land regardless of later failure"
        )
        assert graph.get("PERSON-OK2") is not None, (
            "post-failure op must land — single bad op cannot poison the loop"
        )
        # Bad op did NOT land.
        assert graph.get("PERSON-BAD") is None

        # Exactly one entity.write.failed audit emission, naming the bad op.
        failures = [d for a, d in audit_calls if a == "entity.write.failed"]
        assert len(failures) == 1, (
            f"expected one entity.write.failed audit, got {audit_calls!r}"
        )
        d = failures[0]
        assert d["kind"] == "Person"
        assert d["id"] == "PERSON-BAD"
        assert d["op_index"] == 1
        assert d["workflow_id"] == "WF-ISO"
        assert "error_type" in d and "error_msg" in d
    finally:
        reflector_iso.aclose()
        del PROJECTIONS["test-isolation-domain"]
