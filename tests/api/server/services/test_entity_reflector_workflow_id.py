"""Reflector stamps workflow_id on entity.upserted events (Task B).

Locks the contract that ``EntityReflector._on_event`` mutates each
EntityWrite's ``attrs["workflow_id"]`` so that ``EntityGraph.upsert``
threads it into the FleetEvent payload. Without this, the cosmic-lens
SSE rocket loop (entities mode) discards every entity event because it
keys rockets by workflow_id.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite
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


def test_reflector_stamps_workflow_id_on_entity_upserted_event(
    bus: EventBus, store: StateStore, graph: EntityGraph,
) -> None:
    """A projection that omits workflow_id from attrs still produces an
    ``entity.upserted`` FleetEvent carrying the spawning workflow_id —
    the reflector stamps it on attrs before dispatching to the graph.
    """

    def fake_projection(_wf: Workflow) -> list:
        # Note: attrs deliberately do NOT carry workflow_id — proving the
        # reflector is the layer that stamps it.
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-WFID-1",
                attrs={"name": "Stamped"},
                source_workflows=("WF-test-001",),
            ),
        ]

    captured: list[FleetEvent] = []
    bus.on("entity.upserted", lambda ev: captured.append(ev))

    PROJECTIONS["test-wfid-domain"] = fake_projection
    graph.attach(bus=bus)
    reflector = EntityReflector(bus, store, graph)
    reflector.start()
    try:
        store.upsert_workflow(_make_workflow("WF-test-001", "test-wfid-domain"))
        # Spawning event must carry the originating workflow_id so the
        # reflector can resolve it.
        bus.emit(FleetEvent(type="workflow.completed", workflow_id="WF-test-001"))

        upserts = [e for e in captured if e.type == "entity.upserted"]
        # The reflector now also upserts a Workflow node for every dispatched
        # projection (so SUB_WORKFLOW_OF and the Workflow node table are
        # always populated). Filter that one out before asserting on the
        # projection's own writes.
        person_upserts = [e for e in upserts if e.kind != "Workflow"]
        assert len(person_upserts) == 1, (
            f"expected one Person entity.upserted, got {captured!r}"
        )
        assert person_upserts[0].workflow_id == "WF-test-001", (
            f"reflector failed to stamp workflow_id; got {person_upserts[0]!r}"
        )
        assert person_upserts[0].entity_id == "PERSON-WFID-1"
        assert person_upserts[0].kind == "Person"
    finally:
        reflector.aclose()
        del PROJECTIONS["test-wfid-domain"]


def test_reflector_does_not_clobber_explicit_workflow_id(
    bus: EventBus, store: StateStore, graph: EntityGraph,
) -> None:
    """If a projection already set ``attrs[\"workflow_id\"]`` (e.g. it was
    propagating an upstream id), the reflector must not overwrite it."""

    def fake_projection(_wf: Workflow) -> list:
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-WFID-2",
                attrs={"name": "Pinned", "workflow_id": "WF-upstream-999"},
                source_workflows=("WF-test-002",),
            ),
        ]

    captured: list[FleetEvent] = []
    bus.on("entity.upserted", lambda ev: captured.append(ev))

    PROJECTIONS["test-wfid-pinned"] = fake_projection
    graph.attach(bus=bus)
    reflector = EntityReflector(bus, store, graph)
    reflector.start()
    try:
        store.upsert_workflow(_make_workflow("WF-test-002", "test-wfid-pinned"))
        bus.emit(FleetEvent(type="workflow.completed", workflow_id="WF-test-002"))

        upserts = [e for e in captured if e.type == "entity.upserted"]
        # Skip the Workflow-node upsert the reflector now always emits.
        person_upserts = [e for e in upserts if e.kind != "Workflow"]
        assert len(person_upserts) == 1
        assert person_upserts[0].workflow_id == "WF-upstream-999"
    finally:
        reflector.aclose()
        del PROJECTIONS["test-wfid-pinned"]
