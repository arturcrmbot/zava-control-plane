"""Upsert behaviour for ``EntityGraph`` (TASK-004).

Covers the first write method on the entity graph:

* Insert + read-back via the existing Cypher passthrough (``get`` lands in
  TASK-006, so we read with ``query_one`` directly).
* Re-upserting the same id merges ``attrs`` and dedup-unions
  ``source_workflows`` while preserving insertion order (PAT-004 — the more
  rigorous structural test for that invariant lives in
  ``test_entity_graph_source_workflows.py``).
* Bus + audit each receive exactly one ``entity.upserted`` per call when
  attached.
* Without ``attach()`` the write still happens — bus/audit emission is
  silently skipped. This locks the contract that tests can construct a
  bare graph and exercise upsert without standing up the rest of the
  substrate.
"""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.shared.events import FleetEvent


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


def _read_person(graph: EntityGraph, person_id: str) -> dict:
    row = graph.query_one(
        "MATCH (n:Person) WHERE n.id = $id RETURN n",
        {"id": person_id},
    )
    assert row is not None, f"person {person_id} not found"
    node = row["n"]
    assert isinstance(node, dict)
    return node


def test_upsert_inserts_new_person(graph: EntityGraph) -> None:
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice", "email": "alice@example.com"},
            source_workflows=("bootstrap",),
        )
    )

    node = _read_person(graph, "PERSON-EMP-0001")
    assert node["id"] == "PERSON-EMP-0001"
    assert node["name"] == "Alice"
    assert node["email"] == "alice@example.com"
    assert list(node["source_workflows"]) == ["bootstrap"]


def test_reupsert_merges_attrs_and_dedupes_source_workflows(graph: EntityGraph) -> None:
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice", "email": "alice@example.com"},
            source_workflows=("bootstrap",),
        )
    )
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"department": "Engineering"},
            source_workflows=("VKY-0042",),
        )
    )

    node = _read_person(graph, "PERSON-EMP-0001")
    # Attrs from both upserts coexist (map-merge semantics).
    assert node["name"] == "Alice"
    assert node["email"] == "alice@example.com"
    assert node["department"] == "Engineering"
    # source_workflows is the deduped union, insertion order preserved.
    assert list(node["source_workflows"]) == ["bootstrap", "VKY-0042"]


def test_upsert_emits_bus_and_audit_when_attached(graph: EntityGraph) -> None:
    bus = mock.Mock()
    audit = mock.Mock()
    graph.attach(bus=bus, audit=audit)

    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice", "workflow_id": "VKY-0042"},
            source_workflows=("VKY-0042",),
        )
    )

    # Exactly one event on each.
    assert bus.emit.call_count == 1
    assert audit.log.call_count == 1

    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, FleetEvent)
    assert emitted.type == "entity.upserted"
    assert emitted.workflow_id == "VKY-0042"
    # entity_id + kind ride on the extra-allowed Pydantic fields.
    assert getattr(emitted, "entity_id") == "PERSON-EMP-0001"
    assert getattr(emitted, "kind") == "Person"

    audit_action, audit_details = audit.log.call_args.args
    assert audit_action == "entity.upserted"
    assert audit_details["id"] == "PERSON-EMP-0001"
    assert audit_details["kind"] == "Person"
    assert audit_details["workflow_id"] == "VKY-0042"
    assert audit_details["source_workflows"] == ["VKY-0042"]


def test_upsert_emits_one_event_per_call(graph: EntityGraph) -> None:
    bus = mock.Mock()
    audit = mock.Mock()
    graph.attach(bus=bus, audit=audit)

    for _ in range(3):
        graph.upsert(
            EntityWrite(
                kind="Person",
                id="PERSON-EMP-0001",
                attrs={"name": "Alice"},
                source_workflows=("bootstrap",),
            )
        )

    assert bus.emit.call_count == 3
    assert audit.log.call_count == 3


def test_upsert_without_attach_writes_silently(graph: EntityGraph) -> None:
    # No attach() — bus and audit are still None.
    assert graph.bus is None
    assert graph.audit is None

    # Write still lands in the graph; no AttributeError on missing attach.
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice"},
            source_workflows=("bootstrap",),
        )
    )

    node = _read_person(graph, "PERSON-EMP-0001")
    assert node["name"] == "Alice"
    assert list(node["source_workflows"]) == ["bootstrap"]


def test_upsert_with_only_bus_attached(graph: EntityGraph) -> None:
    bus = mock.Mock()
    graph.attach(bus=bus)
    assert graph.audit is None

    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice"},
            source_workflows=("bootstrap",),
        )
    )

    assert bus.emit.call_count == 1


def test_upsert_with_only_audit_attached(graph: EntityGraph) -> None:
    audit = mock.Mock()
    graph.attach(audit=audit)
    assert graph.bus is None

    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice"},
            source_workflows=("bootstrap",),
        )
    )

    assert audit.log.call_count == 1


def test_upsert_with_empty_attrs_and_no_source_workflows(graph: EntityGraph) -> None:
    # Mid-workflow entities may be created without explicit provenance —
    # the upsert must still land the node with a default empty list.
    graph.upsert(EntityWrite(kind="Person", id="PERSON-EMP-0099", attrs={}))

    node = _read_person(graph, "PERSON-EMP-0099")
    assert node["id"] == "PERSON-EMP-0099"
    assert list(node["source_workflows"]) == []
