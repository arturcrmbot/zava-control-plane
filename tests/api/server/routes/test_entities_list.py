"""GET /api/entities — list with optional ``kind`` and ``limit`` (TASK-031)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


def _seed_mixed(graph) -> None:
    graph.upsert(EntityWrite(kind="Person", id="EMP-A", attrs={"name": "Alice"}))
    graph.upsert(EntityWrite(kind="Person", id="EMP-B", attrs={"name": "Bob"}))
    graph.upsert(EntityWrite(kind="Organisation", id="ORG-1", attrs={"name": "Zava"}))


def test_list_filters_by_kind(graph, client):
    _seed_mixed(graph)
    r = client.get("/api/entities", params={"kind": "Person"})
    assert r.status_code == 200
    body = r.json()
    assert {row["id"] for row in body} == {"EMP-A", "EMP-B"}
    assert all(row["_label"] == "Person" for row in body)


def test_list_no_kind_returns_mixed(graph, client):
    _seed_mixed(graph)
    r = client.get("/api/entities")
    assert r.status_code == 200
    body = r.json()
    labels = {row["_label"] for row in body}
    assert "Person" in labels and "Organisation" in labels
    assert {row["id"] for row in body} == {"EMP-A", "EMP-B", "ORG-1"}


def test_list_honours_limit(graph, client):
    _seed_mixed(graph)
    r = client.get("/api/entities", params={"limit": 2})
    assert r.status_code == 200
    assert len(r.json()) == 2

    r = client.get("/api/entities", params={"kind": "Person", "limit": 1})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_list_invalid_kind_returns_400(graph, client):
    _seed_mixed(graph)
    r = client.get("/api/entities", params={"kind": "NotAKind"})
    assert r.status_code == 400
    assert "unknown entity kind" in r.json()["detail"]
