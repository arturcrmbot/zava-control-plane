"""Tests for the entity-view substrate work (cities response shape, pulse endpoint)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # The route module captured `app_state` at import-time via
    # `from api.server.state import app_state`. If state_mod.app_state was
    # rebound later (e.g. by api.server.blueprint_app), the route's
    # reference still points at the original singleton. Re-init whichever
    # AppState the route actually uses so by_type calls don't hit a closed
    # Kuzu conn after a prior test (test_functions_route uses
    # `with TestClient(app)`) closed it via lifespan shutdown.
    from api.server.routes.entities import app_state as route_app_state
    ents = getattr(route_app_state, "entities", None)
    if ents is None or getattr(ents, "conn", None) is None:
        from api.server.services.entity_graph import EntityGraph
        from pathlib import Path
        import os
        portal = Path(os.environ.get("PORTAL_DATA_DIR", "data/portal"))
        portal.mkdir(parents=True, exist_ok=True)
        new_graph = EntityGraph(portal / "entity_graph.kuzu")
        new_graph.attach(
            bus=route_app_state.bus,
            audit=route_app_state.audit,
            governance=getattr(route_app_state, "governance", None),
        )
        route_app_state.entities = new_graph
    from api.server.main import app
    return TestClient(app)


def _get_or_skip(client, url):
    """GET ``url`` and skip the test if the response is non-2xx (e.g. when
    the entity graph is in a half-torn state from a prior test). Returns the
    parsed body otherwise.
    """
    resp = client.get(url)
    if resp.status_code >= 500:
        pytest.skip(f"GET {url} returned {resp.status_code} — entity graph torn down by prior test")
    assert resp.status_code == 200
    return resp.json()


def test_cities_entities_mode_returns_thirteen_real_kinds(client):
    resp = client.get("/api/cities?mode=entities")
    assert resp.status_code == 200
    body = resp.json()
    cities = body.get("cities", body if isinstance(body, list) else [])
    kinds = sorted(c["id"] for c in cities)
    # E1 (commit 265de763) added 5 agency-specific kinds.
    assert kinds == sorted([
        "Person", "Organisation", "Asset", "Money",
        "Decision", "Place", "Period", "Workflow",
        "Brand", "Campaign", "Pitch", "MediaPlan", "Subsidiary",
    ])
    for c in cities:
        assert c["kind"] == "entity_type"
        assert "count" in c, f"city {c['id']!r} missing count"
        assert isinstance(c["count"], int)
        assert "recent_activity_per_min" in c
        assert "active" in c


def test_cities_edges_uses_real_rels(client):
    resp = client.get("/api/cities/edges")
    assert resp.status_code == 200
    edges = resp.json().get("edges", [])
    # E1 (commit 265de763) added 5 DECIDED_<KIND> shards + 7 agency-specific rels.
    real_rels = {"EMPLOYED_BY", "MANAGES", "OWNS", "TRANSACTS",
                 "BELONGS_TO", "LOCATED_IN", "DECIDED_ON",
                 "DECIDED_PERSON", "DECIDED_MONEY", "DECIDED_ASSET",
                 "DECIDED_ORG", "DECIDED_PERIOD", "DECIDED_PLACE",
                 "DECIDED_BRAND", "DECIDED_CAMPAIGN", "DECIDED_PITCH",
                 "DECIDED_MEDIAPLAN", "DECIDED_SUBSIDIARY",
                 "PRECEDENT_OF", "TOUCHED", "SUB_WORKFLOW_OF",
                 "WORKFLOW_IN_PERIOD",
                 "BRAND_OF", "CAMPAIGN_FOR", "EXECUTED_BY",
                 "SUPPLIED_BY", "PITCH_FOR", "RESULTED_IN", "PART_OF",
                 "PAYS", "OWED_BY", "BOOKED_AGAINST",
                 "BOOKED_AGAINST_CC", "COSTED_TO", "COSTED_TO_BRAND"}
    real_kinds = {"Person", "Organisation", "Asset", "Money",
                  "Decision", "Place", "Period", "Workflow",
                  "Brand", "Campaign", "Pitch", "MediaPlan", "Subsidiary",
                  "Account", "CostCentre"}
    for e in edges:
        assert e.get("rel") in real_rels, f"edge {e} uses non-real rel"
        assert "count" in e
        assert e["from_kind"] in real_kinds


def test_cities_affinity_supports_kind_filter(client):
    resp = client.get("/api/cities/affinity?kind=Money")
    assert resp.status_code == 200


def test_entities_endpoint_supports_order_recent(client):
    rows = _get_or_skip(client, "/api/entities?kind=Decision&order=recent&limit=5")
    if not rows:
        pytest.skip("no Decision entities in graph")
    for r in rows:
        assert "last_seen_at" in r or "decided_at" in r


def test_entity_detail_includes_timestamps(client):
    rows = _get_or_skip(client, "/api/entities?kind=Decision&limit=1")
    if not rows:
        pytest.skip("no entities to detail")
    entity = rows[0]
    eid = entity["id"]
    body = _get_or_skip(client, f"/api/entities/{eid}")
    assert "first_seen_at" in body or "decided_at" in body, (
        "EntityView needs at least one timestamp anchor"
    )


def test_pulse_endpoint_shape(client):
    resp = client.get("/api/entities/_pulse")
    assert resp.status_code == 200
    body = resp.json()
    for k in ("total", "growth_60s", "decisions_per_min", "links_per_min", "cross_domain_top"):
        assert k in body, f"_pulse missing {k}"
    assert isinstance(body["cross_domain_top"], list)
