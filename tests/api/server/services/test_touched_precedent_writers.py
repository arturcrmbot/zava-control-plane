"""Wiring tests for TOUCHED + PRECEDENT_OF (pitch-a5).

Both rel-tables existed in the schema since Phase 1 but had no production
writers — this module pins the two writers that finally land edges:

* ``record_decision`` writes ``Person-[:TOUCHED]->Decision`` when the
  caller's ``persona_role`` is itself a ``PERSON-…`` id (forward-compatible
  with the d2 authority matrix).
* ``query_precedents`` writes ``Decision-[:PRECEDENT_OF]->Decision`` when
  the caller passes ``cite_from_decision_id`` (forward-compatible with
  the i1 precedent-influenced persona policy).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from api.server.mcp_tools.query_precedents import make_query_precedents_tool
from api.server.services.entity_graph import EntityGraph, EntityWrite


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


def _record(graph: EntityGraph, **overrides) -> str:
    kwargs = dict(
        workflow_id="wf-1",
        phase="triage",
        persona_role="approver",
        verdict="approve",
        reason="looks good",
        decided_at=datetime(2025, 1, 1, 12, 0, 0),
        source_event="evt-1",
        attributes={"note": "ok"},
        decided_on=(),
    )
    kwargs.update(overrides)
    return graph.record_decision(**kwargs)


def test_touched_edge_written_when_persona_role_is_person_id(graph: EntityGraph) -> None:
    """A persona_role like ``PERSON-EMP-0001`` lands a TOUCHED edge."""
    person_id = "PERSON-EMP-0001"
    graph.upsert(EntityWrite(kind="Person", id=person_id, attrs={"name": "Ada"}))

    decision_id = _record(graph, persona_role=person_id)

    row = graph.query_one(
        "MATCH (p:Person)-[r:TOUCHED]->(d:Decision) "
        "WHERE p.id = $pid AND d.id = $did "
        "RETURN r.role AS role",
        {"pid": person_id, "did": decision_id},
    )
    assert row is not None, "expected a TOUCHED edge"
    assert row["role"] == person_id


def test_touched_edge_skipped_for_role_string(graph: EntityGraph) -> None:
    """A persona_role like ``cfo`` does NOT write a TOUCHED edge."""
    decision_id = _record(graph, persona_role="cfo")

    row = graph.query_one(
        "MATCH (p:Person)-[r:TOUCHED]->(d:Decision) WHERE d.id = $did "
        "RETURN p.id AS pid",
        {"did": decision_id},
    )
    assert row is None, "expected no TOUCHED edge for non-Person persona_role"


def test_query_precedents_writes_precedent_of_per_row(graph: EntityGraph) -> None:
    """When ``cite_from_decision_id`` is set, one PRECEDENT_OF edge per row."""
    # Mint two precedent decisions on the same persona/entity so the
    # generic precedent query can find them.
    entity_id = "PERSON-VENDOR-77"
    graph.upsert(EntityWrite(kind="Person", id=entity_id, attrs={"name": "Vendor"}))

    prec_a = _record(
        graph,
        workflow_id="wf-prec-a",
        persona_role="ap_clerk",
        decided_on=(entity_id,),
        decided_at=datetime(2025, 1, 1, 10, 0, 0),
    )
    prec_b = _record(
        graph,
        workflow_id="wf-prec-b",
        persona_role="ap_clerk",
        decided_on=(entity_id,),
        decided_at=datetime(2025, 1, 2, 10, 0, 0),
    )

    # Mint the citing Decision (a separate workflow / phase so it doesn't
    # collide with either precedent under PAT-001 dedupe).
    citing = _record(
        graph,
        workflow_id="wf-citer",
        phase="review",
        persona_role="ap_clerk",
    )

    tool = make_query_precedents_tool(graph)
    rows = tool(
        "ap_clerk",
        entity_id,
        limit=10,
        cite_from_decision_id=citing,
    )
    returned_ids = {row["d"]["id"] for row in rows}
    assert {prec_a, prec_b}.issubset(returned_ids)

    edges = graph.query(
        "MATCH (a:Decision)-[:PRECEDENT_OF]->(b:Decision) "
        "WHERE a.id = $cid RETURN b.id AS target",
        {"cid": citing},
    )
    targets = {row["target"] for row in edges}
    # Exactly one edge per row returned by the precedent query.
    assert targets == returned_ids
    assert len(targets) == len(rows)
