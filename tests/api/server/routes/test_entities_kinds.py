"""GET /api/entities/_kinds — per-kind summary for the Org X-ray panel
(pitch-a7)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


# Mirror of `_KINDS` in api/server/routes/entities.py — kept inline so a
# rename here flags up as a test failure rather than passing silently.
_EXPECTED_KINDS: tuple[str, ...] = (
    "Person", "Organisation", "Asset", "Money",
    "Decision", "Place", "Period", "Workflow",
    # E1 added these 5 agency-specific kinds (commit 265de763).
    "Brand", "Campaign", "Pitch", "MediaPlan", "Subsidiary",
    # Phase 2: accounts substrate
    "Account", "CostCentre",
    # autonomous-domain-insights v1: persona-emitted insight kind
    "Insight",
)


def _seed(graph) -> None:
    # Two people, three orgs, one asset, one money, three decisions.
    graph.upsert(EntityWrite(kind="Person", id="P-1", attrs={"name": "Alice"}))
    graph.upsert(EntityWrite(kind="Person", id="P-2", attrs={"name": "Bob"}))
    graph.upsert(EntityWrite(kind="Organisation", id="O-1", attrs={"name": "OrgA"}))
    graph.upsert(EntityWrite(kind="Organisation", id="O-2", attrs={"name": "OrgB"}))
    graph.upsert(EntityWrite(kind="Organisation", id="O-3", attrs={"name": "OrgC"}))
    graph.upsert(EntityWrite(kind="Organisation", id="O-4", attrs={"name": "OrgD"}))
    graph.upsert(EntityWrite(kind="Asset", id="A-1", attrs={"identifier": "msa"}))
    graph.upsert(EntityWrite(kind="Money", id="M-1", attrs={"amount": 100.0}))
    graph.link("P-1", "EMPLOYED_BY", "O-1", role="eng")
    graph.link("P-2", "EMPLOYED_BY", "O-1", role="ops")
    graph.link("P-1", "OWNS", "A-1")
    graph.link("P-1", "TRANSACTS", "M-1", role="payer")


def test_kinds_lists_every_kind(graph, client):
    _seed(graph)
    r = client.get("/api/entities/_kinds")
    assert r.status_code == 200
    body = r.json()
    assert "kinds" in body
    seen = {row["kind"] for row in body["kinds"]}
    assert seen == set(_EXPECTED_KINDS)


def test_kinds_sample_ids_capped_at_three(graph, client):
    _seed(graph)
    r = client.get("/api/entities/_kinds")
    assert r.status_code == 200
    body = r.json()
    by_kind = {row["kind"]: row for row in body["kinds"]}
    # Organisation has 4 seeded — sample_ids must still be capped at 3.
    assert len(by_kind["Organisation"]["sample_ids"]) == 3
    # Every kind row obeys the ≤3 cap, including the empty kinds.
    for row in body["kinds"]:
        assert len(row["sample_ids"]) <= 3
        assert all(isinstance(sid, str) and sid for sid in row["sample_ids"])


def test_kinds_counts_match_count_by_kind(graph, client):
    _seed(graph)
    expected = graph.count_by_kind()
    r = client.get("/api/entities/_kinds")
    assert r.status_code == 200
    body = r.json()
    actual = {row["kind"]: row["count"] for row in body["kinds"]}
    for kind, exp in expected.items():
        assert actual[kind] == exp, f"count mismatch for {kind}: got {actual[kind]} expected {exp}"


def test_kinds_recent_link_count_present(graph, client):
    _seed(graph)
    r = client.get("/api/entities/_kinds")
    body = r.json()
    by_kind = {row["kind"]: row for row in body["kinds"]}
    # Person has the most edges in the seed (EMPLOYED_BY, OWNS, TRANSACTS,
    # both directions counted by the undirected MATCH); should be > 0.
    assert by_kind["Person"]["recent_link_count"] > 0
    # An untouched kind reports 0, not missing.
    assert by_kind["Period"]["recent_link_count"] == 0


def test_kinds_route_not_swallowed_by_id_route(graph, client):
    """``/_kinds`` must not be matched as ``/{id}`` and 404."""
    r = client.get("/api/entities/_kinds")
    assert r.status_code == 200
    assert "kinds" in r.json()
