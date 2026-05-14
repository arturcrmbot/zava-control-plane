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
    assert r.headers.get("X-Total-Count") == "0"


def test_linked_pagination(graph, client):
    graph.upsert(EntityWrite(kind="Organisation", id="ORG-HUB", attrs={"name": "Hub"}))
    for i in range(7):
        emp_id = f"EMP-{i:03d}"
        graph.upsert(EntityWrite(kind="Person", id=emp_id, attrs={"name": f"P{i}"}))
        graph.link(emp_id, "EMPLOYED_BY", "ORG-HUB", role="x")

    # Default returns the lot for a small fixture and stamps total.
    r = client.get("/api/entities/ORG-HUB/linked")
    assert r.status_code == 200
    assert r.headers["X-Total-Count"] == "7"
    assert len(r.json()) == 7

    # limit clamps the page; total still reflects the un-paginated count.
    r = client.get("/api/entities/ORG-HUB/linked", params={"limit": 3})
    assert r.status_code == 200
    assert r.headers["X-Total-Count"] == "7"
    body = r.json()
    assert len(body) == 3

    # offset advances; combined with limit it slices.
    r2 = client.get("/api/entities/ORG-HUB/linked", params={"limit": 3, "offset": 3})
    assert r2.status_code == 200
    assert r2.headers["X-Total-Count"] == "7"
    body2 = r2.json()
    assert len(body2) == 3
    page_one_ids = {row["entity"]["id"] for row in body}
    page_two_ids = {row["entity"]["id"] for row in body2}
    assert page_one_ids.isdisjoint(page_two_ids)

    # offset past the end is empty, not an error.
    r3 = client.get("/api/entities/ORG-HUB/linked", params={"offset": 99})
    assert r3.status_code == 200
    assert r3.json() == []
    assert r3.headers["X-Total-Count"] == "7"


def test_linked_limit_validation(graph, client):
    graph.upsert(EntityWrite(kind="Person", id="EMP-V", attrs={"name": "V"}))
    # limit must be 1..500
    assert client.get("/api/entities/EMP-V/linked", params={"limit": 0}).status_code == 422
    assert client.get("/api/entities/EMP-V/linked", params={"limit": 501}).status_code == 422
    assert client.get("/api/entities/EMP-V/linked", params={"offset": -1}).status_code == 422
