"""Read-method behaviour for ``EntityGraph`` (TASK-006).

Covers the four read helpers the substrate hands to MCP tools and to
projection-side code that needs to look entities up by id, kind, rel, or
workflow provenance:

* :meth:`EntityGraph.get` — label-less MATCH by id across all eight kinds.
* :meth:`EntityGraph.by_type` — typed MATCH with optional attribute filters.
* :meth:`EntityGraph.linked` — outgoing neighbours, optionally filtered by
  rel type (with the same case-normalisation as :meth:`EntityGraph.link`).
* :meth:`EntityGraph.touched_by` — every entity whose ``source_workflows``
  contains a given workflow id.

Seeds use :meth:`EntityGraph.upsert` and :meth:`EntityGraph.link` so the
tests exercise the full write→read round-trip as the substrate sees it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


def _seed_two_persons_and_org(graph: EntityGraph) -> None:
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="EMP-1",
            attrs={"name": "Alice", "role": "engineer"},
            source_workflows=("WF-A",),
        )
    )
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="EMP-2",
            attrs={"name": "Bob", "role": "manager"},
            source_workflows=("WF-B",),
        )
    )
    graph.upsert(
        EntityWrite(
            kind="Organisation",
            id="ORG-1",
            attrs={"name": "Zava"},
            source_workflows=("WF-A", "WF-B"),
        )
    )


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_returns_person_by_id(graph: EntityGraph) -> None:
    _seed_two_persons_and_org(graph)
    node = graph.get("EMP-1")
    assert node is not None
    assert node["id"] == "EMP-1"
    assert node["name"] == "Alice"
    # Label-less MATCH carries Kuzu's _label sentinel so callers can tell
    # which node table the row came from.
    assert node["_label"] == "Person"


def test_get_returns_organisation_when_id_resolves_there(graph: EntityGraph) -> None:
    _seed_two_persons_and_org(graph)
    node = graph.get("ORG-1")
    assert node is not None
    assert node["_label"] == "Organisation"
    assert node["name"] == "Zava"


def test_get_returns_none_when_id_does_not_exist(graph: EntityGraph) -> None:
    _seed_two_persons_and_org(graph)
    assert graph.get("NOPE") is None


# ---------------------------------------------------------------------------
# by_type
# ---------------------------------------------------------------------------


def test_by_type_returns_all_of_kind(graph: EntityGraph) -> None:
    _seed_two_persons_and_org(graph)
    persons = graph.by_type("Person")
    assert {p["id"] for p in persons} == {"EMP-1", "EMP-2"}


def test_by_type_filter_narrows_results(graph: EntityGraph) -> None:
    _seed_two_persons_and_org(graph)
    managers = graph.by_type("Person", role="manager")
    assert len(managers) == 1
    assert managers[0]["id"] == "EMP-2"


def test_by_type_returns_empty_list_when_no_match(graph: EntityGraph) -> None:
    _seed_two_persons_and_org(graph)
    assert graph.by_type("Asset") == []
    assert graph.by_type("Person", role="ceo") == []


def test_by_type_unknown_kind_raises_valueerror(graph: EntityGraph) -> None:
    with pytest.raises(ValueError, match="unknown entity kind"):
        graph.by_type("Banana")


def test_by_type_invalid_filter_key_raises_valueerror(graph: EntityGraph) -> None:
    with pytest.raises(ValueError, match="invalid filter key"):
        # Backtick-injection attempt: the regex rejects it before any
        # Cypher is built.
        graph.by_type("Person", **{"role`; DROP TABLE Person; --": "x"})


# ---------------------------------------------------------------------------
# linked
# ---------------------------------------------------------------------------


def _seed_links(graph: EntityGraph) -> None:
    _seed_two_persons_and_org(graph)
    graph.upsert(
        EntityWrite(
            kind="Asset",
            id="LAPTOP-1",
            attrs={"identifier": "MBP-001"},
            source_workflows=("WF-A",),
        )
    )
    graph.link("EMP-1", "EMPLOYED_BY", "ORG-1", role="engineer")
    graph.link("EMP-1", "OWNS", "LAPTOP-1")


def test_linked_returns_all_outgoing_when_rel_is_none(graph: EntityGraph) -> None:
    _seed_links(graph)
    rows = graph.linked("EMP-1")
    rels = {row["rel"] for row in rows}
    assert rels == {"EMPLOYED_BY", "OWNS"}
    targets = {row["node"]["id"] for row in rows}
    assert targets == {"ORG-1", "LAPTOP-1"}


def test_linked_filtered_by_rel_returns_only_that_type(graph: EntityGraph) -> None:
    _seed_links(graph)
    rows = graph.linked("EMP-1", rel="EMPLOYED_BY")
    assert len(rows) == 1
    assert rows[0]["rel"] == "EMPLOYED_BY"
    assert rows[0]["node"]["id"] == "ORG-1"


def test_linked_normalises_lowercase_rel(graph: EntityGraph) -> None:
    _seed_links(graph)
    rows = graph.linked("EMP-1", rel="employed_by")
    assert len(rows) == 1
    assert rows[0]["rel"] == "EMPLOYED_BY"


def test_linked_returns_empty_when_no_outgoing(graph: EntityGraph) -> None:
    _seed_links(graph)
    # EMP-2 was seeded but never linked.
    assert graph.linked("EMP-2") == []


def test_linked_returns_empty_for_unknown_id(graph: EntityGraph) -> None:
    _seed_links(graph)
    assert graph.linked("NOPE") == []


def test_linked_unknown_rel_raises_valueerror(graph: EntityGraph) -> None:
    _seed_links(graph)
    with pytest.raises(ValueError, match="unknown rel"):
        graph.linked("EMP-1", rel="DOES_NOT_EXIST")


def test_linked_is_outgoing_only(graph: EntityGraph) -> None:
    """linked(id) returns OUTGOING rels only.

    Locks the direction semantic — accidental change to undirected
    ``-[r]-`` or reverse ``<-[r]-`` patterns would silently break this
    contract.
    """
    _seed_links(graph)

    # From the source: 1 outgoing EMPLOYED_BY rel.
    assert len(graph.linked("EMP-1", rel="EMPLOYED_BY")) == 1

    # From the target: 0 outgoing rels (the EMPLOYED_BY edge is incoming
    # from ORG-1's perspective, not outgoing).
    assert graph.linked("ORG-1", rel="EMPLOYED_BY") == []
    assert graph.linked("ORG-1") == []


# ---------------------------------------------------------------------------
# touched_by
# ---------------------------------------------------------------------------


def test_touched_by_returns_entities_across_kinds(graph: EntityGraph) -> None:
    _seed_two_persons_and_org(graph)
    rows = graph.touched_by("WF-A")
    ids = {r["id"] for r in rows}
    # EMP-1 has source_workflows=(WF-A,); ORG-1 has (WF-A, WF-B).
    assert ids == {"EMP-1", "ORG-1"}
    labels = {r["_label"] for r in rows}
    assert labels == {"Person", "Organisation"}


def test_touched_by_returns_only_matching_entities(graph: EntityGraph) -> None:
    _seed_two_persons_and_org(graph)
    rows = graph.touched_by("WF-B")
    assert {r["id"] for r in rows} == {"EMP-2", "ORG-1"}


def test_touched_by_returns_empty_list_when_no_entity_touches_workflow(graph: EntityGraph) -> None:
    _seed_two_persons_and_org(graph)
    assert graph.touched_by("WF-NEVER-USED") == []
