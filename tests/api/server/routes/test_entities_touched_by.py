"""GET /api/entities/touched-by/{wf_id} (TASK-034)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


def test_touched_by_returns_only_matching_workflow(graph, client):
    graph.upsert(EntityWrite(
        kind="Person", id="EMP-1", attrs={"name": "Alice"},
        source_workflows=("WF-AP-001",),
    ))
    graph.upsert(EntityWrite(
        kind="Organisation", id="ORG-1", attrs={"name": "Zava"},
        source_workflows=("WF-AP-001",),
    ))
    graph.upsert(EntityWrite(
        kind="Person", id="EMP-2", attrs={"name": "Bob"},
        source_workflows=("WF-AP-999",),
    ))

    r = client.get("/api/entities/touched-by/WF-AP-001")
    assert r.status_code == 200
    body = r.json()
    assert {row["id"] for row in body} == {"EMP-1", "ORG-1"}


def test_touched_by_unknown_workflow_returns_empty(graph, client):
    r = client.get("/api/entities/touched-by/WF-NONE")
    assert r.status_code == 200
    assert r.json() == []
