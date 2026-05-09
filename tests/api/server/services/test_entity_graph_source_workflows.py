"""Source-workflows union invariant for ``EntityGraph.upsert`` (TASK-008c, PAT-004).

Locks the structural contract called out in the plan: when an entity is
upserted multiple times, ``source_workflows`` is the **deduped union** of
all values seen, with **insertion order preserved**. This is what gives
the Phase 4 meta-workflow projection a deterministic provenance trail per
node — duplicates are silently dropped, but order tells you which
workflow first touched the entity.

This file deliberately stands alone (no shared fixtures with TASK-004's
test file) because PAT-004 is a structural invariant the plan calls out
as something to lock independently of the wider upsert behaviour suite.
"""
from __future__ import annotations

from pathlib import Path

from api.server.services.entity_graph import EntityGraph, EntityWrite


def _stored_source_workflows(graph: EntityGraph, person_id: str) -> list[str]:
    row = graph.query_one(
        "MATCH (n:Person) WHERE n.id = $id RETURN n.source_workflows AS sw",
        {"id": person_id},
    )
    assert row is not None, f"person {person_id} not found"
    return list(row["sw"])


def test_source_workflows_union_preserves_insertion_order(tmp_path: Path) -> None:
    graph = EntityGraph(tmp_path / "g.kuzu")

    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice"},
            source_workflows=("bootstrap",),
        )
    )
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice"},
            source_workflows=("VKY-0042",),
        )
    )

    assert _stored_source_workflows(graph, "PERSON-EMP-0001") == [
        "bootstrap",
        "VKY-0042",
    ]


def test_source_workflows_union_dedupes_overlapping_entries(tmp_path: Path) -> None:
    graph = EntityGraph(tmp_path / "g.kuzu")

    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice"},
            source_workflows=("bootstrap",),
        )
    )
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice"},
            source_workflows=("VKY-0042",),
        )
    )
    # Third upsert overlaps with the first ("bootstrap") and adds a new
    # workflow id ("PORD-0099"). Bootstrap must NOT be duplicated and the
    # new id appends to the tail.
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice"},
            source_workflows=("bootstrap", "PORD-0099"),
        )
    )

    assert _stored_source_workflows(graph, "PERSON-EMP-0001") == [
        "bootstrap",
        "VKY-0042",
        "PORD-0099",
    ]


def test_source_workflows_dedupes_within_single_upsert(tmp_path: Path) -> None:
    # Even a single upsert with internal duplicates should dedupe — the
    # union semantic is "set with insertion order", not "concat then
    # dedupe across upserts only".
    graph = EntityGraph(tmp_path / "g.kuzu")

    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0001",
            attrs={"name": "Alice"},
            source_workflows=("bootstrap", "VKY-0042", "bootstrap"),
        )
    )

    assert _stored_source_workflows(graph, "PERSON-EMP-0001") == [
        "bootstrap",
        "VKY-0042",
    ]
