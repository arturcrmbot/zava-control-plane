"""GET /api/entities/{id} — single entity lookup, 404 on miss (TASK-032)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


def test_get_entity_hit(graph, client):
    graph.upsert(EntityWrite(kind="Person", id="EMP-1", attrs={"name": "Alice"}))
    r = client.get("/api/entities/EMP-1")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "EMP-1"
    assert body["name"] == "Alice"
    assert body["_label"] == "Person"


def test_get_entity_404(graph, client):
    r = client.get("/api/entities/DOES-NOT-EXIST")
    assert r.status_code == 404
