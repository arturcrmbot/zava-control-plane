"""Person upsert merge semantics — Phase 1 ghost-person fix.

When a projection later reflects a fully-attributed Person, the upsert
must NOT blank out fields that were populated by an earlier seed write.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


def test_seed_then_projection_does_not_blank_name(graph: EntityGraph):
    # Phase 1: full named seed from DataPack
    graph.upsert(EntityWrite(
        kind="Person", id="PERSON-EMP-0042",
        attrs={"name": "Aisha Khan", "email": "aisha@zava", "role": "ap_clerk"},
    ))
    # Phase 2: a workflow projection later references the same id with no attrs
    graph.upsert(EntityWrite(
        kind="Person", id="PERSON-EMP-0042",
        attrs={},
        source_workflows=("API-0001",),
    ))
    rows = graph.query(
        "MATCH (p:Person {id: 'PERSON-EMP-0042'}) RETURN p.name, p.role"
    )
    assert rows[0]["p.name"] == "Aisha Khan"
    assert rows[0]["p.role"] == "ap_clerk"


def test_seed_then_projection_does_not_blank_name_with_explicit_empty(graph: EntityGraph):
    """Real ghost-Person path: a projection upserts the same id with
    explicit ``None`` / empty-string values rather than an empty dict.

    Before the ``skip_empty=True`` guard in ``_build_set_clauses``, this
    second upsert blanked the populated columns. With the guard, the
    empty values are dropped before the SET clauses are built.
    """
    graph.upsert(EntityWrite(
        kind="Person", id="PERSON-EMP-0099",
        attrs={"name": "Jin Park", "email": "jin@zava", "role": "engineer"},
    ))
    graph.upsert(EntityWrite(
        kind="Person", id="PERSON-EMP-0099",
        attrs={"name": None, "role": ""},
        source_workflows=("API-0002",),
    ))
    rows = graph.query(
        "MATCH (p:Person {id: 'PERSON-EMP-0099'}) RETURN p.name, p.role, p.email"
    )
    assert rows[0]["p.name"] == "Jin Park"
    assert rows[0]["p.role"] == "engineer"
    assert rows[0]["p.email"] == "jin@zava"
