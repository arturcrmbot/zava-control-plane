"""GET /api/network/holding-view — network-effects panel (pitch-e6)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


_EXPECTED_KEYS = {"subsidiaries", "talent_flows", "client_overlap"}


def _seed_five_subsidiaries(g) -> None:
    for sid, name, country, hc in (
        ("ORG-zava-creative", "Zava Creative", "UK", 22),
        ("ORG-zava-media", "Zava Media", "US", 18),
        ("ORG-zava-production", "Zava Production", "DE", 25),
        ("ORG-zava-data", "Zava Data", "UK", 14),
        ("ORG-zava-group", "Zava Group", "UK", 20),
    ):
        g.upsert(EntityWrite(
            kind="Subsidiary", id=sid,
            attrs={"name": name, "country": country, "headcount": hc},
        ))


def test_holding_view_returns_200(graph, client):
    r = client.get("/api/network/holding-view")
    assert r.status_code == 200


def test_holding_view_shape_intact_on_empty_graph(graph, client):
    r = client.get("/api/network/holding-view")
    body = r.json()
    assert set(body.keys()) == _EXPECTED_KEYS
    # All three sections are lists, even when the graph is empty.
    assert body["subsidiaries"] == []
    assert body["talent_flows"] == []
    assert body["client_overlap"] == []


def test_holding_view_returns_five_subsidiaries(graph, client):
    _seed_five_subsidiaries(graph)
    r = client.get("/api/network/holding-view")
    body = r.json()
    assert len(body["subsidiaries"]) == 5
    # Each carries the documented contract.
    for s in body["subsidiaries"]:
        assert set(s.keys()) == {
            "id", "name", "headcount", "brands",
            "clients", "billable_utilisation_pct", "country",
        }
        assert isinstance(s["brands"], list)
        assert isinstance(s["clients"], list)
        assert isinstance(s["headcount"], int)
        assert 0 <= s["billable_utilisation_pct"] <= 100


def test_holding_view_headcount_uses_static_when_no_employed_by(graph, client):
    _seed_five_subsidiaries(graph)
    r = client.get("/api/network/holding-view")
    body = r.json()
    by_id = {s["id"]: s for s in body["subsidiaries"]}
    assert by_id["ORG-zava-creative"]["headcount"] == 22
    assert by_id["ORG-zava-data"]["headcount"] == 14


def test_holding_view_skips_subsidiary_with_blank_id(graph, client):
    # Even garbage data on the wire mustn't 500 the panel. The route
    # filters out non-string / empty ids defensively.
    graph.upsert(EntityWrite(
        kind="Subsidiary", id="ORG-zava-real",
        attrs={"name": "Real Sub", "country": "UK", "headcount": 5},
    ))
    r = client.get("/api/network/holding-view")
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()["subsidiaries"]]
    assert "ORG-zava-real" in ids
    assert "" not in ids


def test_holding_view_talent_flows_empty_without_workflow(graph, client):
    # No intercompany_talent_transfer workflows exist in the fixture
    # graph, so the flows list must be empty (not crash).
    _seed_five_subsidiaries(graph)
    r = client.get("/api/network/holding-view")
    assert r.json()["talent_flows"] == []


def test_holding_view_client_overlap_lists_clients_when_no_chain(graph, client):
    # Until the BRAND_OF + EXECUTED_BY chain is populated, the route
    # falls back to listing each client with subsidiary_count = 0.
    graph.upsert(EntityWrite(
        kind="Organisation", id="ORG-client-soylent-group",
        attrs={"name": "Soylent Group", "kind": "client"},
    ))
    r = client.get("/api/network/holding-view")
    overlap = r.json()["client_overlap"]
    assert len(overlap) == 1
    assert overlap[0]["client_id"] == "ORG-client-soylent-group"
    assert overlap[0]["subsidiary_count"] == 0
    assert overlap[0]["subsidiaries"] == []


def test_holding_view_subsidiaries_sorted_by_name(graph, client):
    _seed_five_subsidiaries(graph)
    r = client.get("/api/network/holding-view")
    names = [s["name"] for s in r.json()["subsidiaries"]]
    assert names == sorted(names)
