"""GET /api/entities/_stats — counts / hot / recentLinks (TASK-035)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


def test_stats_empty_has_all_fifteen_kinds(graph, client):
    r = client.get("/api/entities/_stats")
    assert r.status_code == 200
    body = r.json()
    counts = body["counts"]
    # 8 originals + 5 agency-specific kinds (E1, commit 265de763)
    # + 2 accounts-substrate kinds added in Phase 2
    # + 1 Insight kind added in autonomous-domain-insights v1.
    assert set(counts.keys()) == {
        "Person", "Organisation", "Asset", "Money",
        "Decision", "Place", "Period", "Workflow",
        "Brand", "Campaign", "Pitch", "MediaPlan", "Subsidiary",
        "Account", "CostCentre",
        "Insight",
    }
    assert all(v == 0 for v in counts.values())
    assert body["hot"] == []
    assert body["recentLinks"] == []


def test_stats_hot_lists_entities_with_source_workflows(graph, client):
    graph.upsert(EntityWrite(
        kind="Person", id="EMP-A", attrs={"name": "Alice"},
        source_workflows=("W1", "W2", "W3"),
    ))
    graph.upsert(EntityWrite(
        kind="Person", id="EMP-B", attrs={"name": "Bob"},
        source_workflows=("W1",),
    ))
    # Person without source_workflows — must NOT appear in hot.
    graph.upsert(EntityWrite(kind="Person", id="EMP-C", attrs={"name": "Carol"}))

    r = client.get("/api/entities/_stats")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["Person"] == 3
    hot_ids = [row["id"] for row in body["hot"]]
    assert hot_ids[:2] == ["EMP-A", "EMP-B"]
    assert "EMP-C" not in hot_ids


def test_stats_recent_links_includes_seeded_rel(graph, client):
    graph.upsert(EntityWrite(kind="Person", id="EMP-1", attrs={"name": "Alice"}))
    graph.upsert(EntityWrite(kind="Organisation", id="ORG-1", attrs={"name": "Zava"}))
    graph.link("EMP-1", "EMPLOYED_BY", "ORG-1")

    r = client.get("/api/entities/_stats")
    assert r.status_code == 200
    body = r.json()
    assert len(body["recentLinks"]) == 1
    link = body["recentLinks"][0]
    assert link["rel"] == "EMPLOYED_BY"
    assert link["src"]["id"] == "EMP-1"
    assert link["dst"]["id"] == "ORG-1"
