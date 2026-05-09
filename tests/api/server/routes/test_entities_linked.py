"""GET /api/entities/{id}/linked — outgoing neighbours (TASK-033)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


def _seed_employed(graph) -> None:
    graph.upsert(EntityWrite(kind="Person", id="EMP-1", attrs={"name": "Alice"}))
    graph.upsert(EntityWrite(kind="Organisation", id="ORG-1", attrs={"name": "Zava"}))
    graph.link("EMP-1", "EMPLOYED_BY", "ORG-1", role="engineer")


def test_linked_unfiltered(graph, client):
    _seed_employed(graph)
    r = client.get("/api/entities/EMP-1/linked")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    row = body[0]
    assert row["rel"] == "EMPLOYED_BY"
    assert row["entity"]["id"] == "ORG-1"
    assert row["entity"]["_label"] == "Organisation"
    # Renamed key — the EntityGraph layer uses "node"; the route flips it
    # to "entity" per the Phase 1 plan response shape.
    assert "node" not in row


def test_linked_filtered_by_rel_lowercase(graph, client):
    _seed_employed(graph)
    r = client.get("/api/entities/EMP-1/linked", params={"rel": "employed_by"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["rel"] == "EMPLOYED_BY"


def test_linked_unknown_rel_returns_400(graph, client):
    _seed_employed(graph)
    r = client.get("/api/entities/EMP-1/linked", params={"rel": "NOT_A_REL"})
    assert r.status_code == 400


def test_linked_no_neighbours(graph, client):
    graph.upsert(EntityWrite(kind="Person", id="EMP-LONE", attrs={"name": "Lone"}))
    r = client.get("/api/entities/EMP-LONE/linked")
    assert r.status_code == 200
    assert r.json() == []
