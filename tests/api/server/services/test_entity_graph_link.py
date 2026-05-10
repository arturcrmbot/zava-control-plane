"""Relationship-write behaviour for ``EntityGraph.link`` (TASK-005).

Covers the second write method on the entity graph:

* MERGE-based rel insert with per-key SET clauses (Kuzu 0.6.1 doesn't
  support ``SET r += $map``) reads back through the Cypher passthrough.
* Re-link is idempotent — repeated calls with the same
  ``(src_id, rel, dst_id)`` triple update attrs in-place rather than
  duplicating the rel record.
* Unknown rel raises a clean ``ValueError`` (mirroring the ``upsert``
  kind whitelist) before any Cypher hits Kuzu.
* Bus + audit each receive exactly one ``entity.linked`` per call when
  attached — without ``attach()`` the write still happens, emission is
  silently skipped (mirrors ``test_upsert_without_attach_writes_silently``).
* Invalid attr keys raise ``ValueError`` (defense-in-depth against
  identifier injection — mirrors
  ``test_upsert_invalid_attr_key_raises_valueerror``).
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


def _seed_person_and_org(graph: EntityGraph) -> None:
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="EMP-1",
            attrs={"name": "Alice"},
            source_workflows=("bootstrap",),
        )
    )
    graph.upsert(
        EntityWrite(
            kind="Organisation",
            id="ORG-1",
            attrs={"name": "Zava"},
            source_workflows=("bootstrap",),
        )
    )


def test_link_creates_rel_with_attrs(graph: EntityGraph) -> None:
    """TASK-005 reads back via Cypher passthrough; TASK-006 will add the
    ``linked()`` helper to wrap this query for callers."""
    _seed_person_and_org(graph)

    graph.link("EMP-1", "employed_by", "ORG-1", role="engineer")

    row = graph.query_one(
        "MATCH (p:Person)-[r:EMPLOYED_BY]->(o:Organisation) "
        "WHERE p.id = $pid RETURN o.id AS oid, r.role AS role",
        {"pid": "EMP-1"},
    )
    assert row is not None, "EMPLOYED_BY rel not found"
    assert row["oid"] == "ORG-1"
    assert row["role"] == "engineer"


def test_relink_is_idempotent_and_updates_attrs(graph: EntityGraph) -> None:
    _seed_person_and_org(graph)

    graph.link("EMP-1", "employed_by", "ORG-1", role="engineer")
    graph.link("EMP-1", "employed_by", "ORG-1", role="senior-engineer")

    count_row = graph.query_one(
        "MATCH ()-[r:EMPLOYED_BY]->() RETURN count(r) AS n"
    )
    assert count_row is not None
    assert count_row["n"] == 1, "second link() created a duplicate rel"

    attr_row = graph.query_one(
        "MATCH (p:Person)-[r:EMPLOYED_BY]->(o:Organisation) "
        "WHERE p.id = $pid RETURN r.role AS role",
        {"pid": "EMP-1"},
    )
    assert attr_row is not None
    assert attr_row["role"] == "senior-engineer", "second link() did not update attrs"


def test_link_accepts_uppercase_rel(graph: EntityGraph) -> None:
    """Both ``employed_by`` and ``EMPLOYED_BY`` must resolve to the same
    rel table — the implementation normalises to uppercase."""
    _seed_person_and_org(graph)

    graph.link("EMP-1", "EMPLOYED_BY", "ORG-1", role="engineer")

    row = graph.query_one(
        "MATCH (p:Person)-[r:EMPLOYED_BY]->(o:Organisation) "
        "WHERE p.id = $pid RETURN o.id AS oid",
        {"pid": "EMP-1"},
    )
    assert row is not None
    assert row["oid"] == "ORG-1"


def test_link_unknown_rel_raises_valueerror(graph: EntityGraph) -> None:
    _seed_person_and_org(graph)

    with pytest.raises(ValueError, match="unknown rel"):
        graph.link("EMP-1", "lives_with", "ORG-1")


def test_link_emits_bus_and_audit_when_attached(graph: EntityGraph) -> None:
    _seed_person_and_org(graph)

    bus = mock.Mock()
    audit = mock.Mock()
    graph.attach(bus=bus, audit=audit)

    graph.link("EMP-1", "employed_by", "ORG-1", role="engineer")

    assert bus.emit.call_count == 1
    assert audit.log.call_count == 1

    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, FleetEvent)
    assert emitted.type == "entity.linked"
    # src_id / dst_id / rel ride on the extra-allowed Pydantic fields.
    assert getattr(emitted, "src_id") == "EMP-1"
    assert getattr(emitted, "dst_id") == "ORG-1"
    assert getattr(emitted, "rel") == "EMPLOYED_BY"

    audit_action, audit_details = audit.log.call_args.args
    assert audit_action == "entity.linked"
    assert audit_details["src_id"] == "EMP-1"
    assert audit_details["dst_id"] == "ORG-1"
    assert audit_details["rel"] == "EMPLOYED_BY"


def test_link_emits_one_event_per_call(graph: EntityGraph) -> None:
    _seed_person_and_org(graph)

    bus = mock.Mock()
    audit = mock.Mock()
    graph.attach(bus=bus, audit=audit)

    for _ in range(3):
        graph.link("EMP-1", "employed_by", "ORG-1", role="engineer")

    assert bus.emit.call_count == 3
    assert audit.log.call_count == 3


def test_link_without_attach_writes_silently(graph: EntityGraph) -> None:
    _seed_person_and_org(graph)
    assert graph.bus is None
    assert graph.audit is None

    # Should not raise; rel still lands in the graph.
    graph.link("EMP-1", "employed_by", "ORG-1", role="engineer")

    row = graph.query_one(
        "MATCH (p:Person)-[r:EMPLOYED_BY]->(o:Organisation) "
        "WHERE p.id = $pid RETURN r.role AS role",
        {"pid": "EMP-1"},
    )
    assert row is not None
    assert row["role"] == "engineer"


def test_link_invalid_attr_key_raises_valueerror(graph: EntityGraph) -> None:
    _seed_person_and_org(graph)

    with pytest.raises(ValueError, match="invalid attr key"):
        graph.link("EMP-1", "employed_by", "ORG-1", **{"role; DROP": "engineer"})


def test_link_with_no_attrs(graph: EntityGraph) -> None:
    """Some rels have no attributes (e.g. OWNS). ``link`` must build a
    valid Cypher statement when ``**attrs`` is empty (no SET clause)."""
    graph.upsert(EntityWrite(kind="Person", id="EMP-2", attrs={"name": "Bob"}))
    graph.upsert(
        EntityWrite(
            kind="Asset",
            id="ASSET-1",
            attrs={"identifier": "laptop-42"},
        )
    )

    graph.link("EMP-2", "owns", "ASSET-1")

    row = graph.query_one(
        "MATCH (p:Person)-[:OWNS]->(a:Asset) WHERE p.id = $pid RETURN a.id AS aid",
        {"pid": "EMP-2"},
    )
    assert row is not None
    assert row["aid"] == "ASSET-1"
