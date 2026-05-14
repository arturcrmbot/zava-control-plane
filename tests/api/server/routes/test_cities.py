"""Tests for /api/cities — cosmic-lens v2 city roster + affinity."""

from fastapi.testclient import TestClient

from api.server.main import app


client = TestClient(app)


def test_cities_capabilities_returns_mixed_kinds():
    r = client.get("/api/cities?mode=capabilities")
    assert r.status_code == 200
    data = r.json()
    assert "cities" in data
    assert data["mode"] == "capabilities"
    cities = data["cities"]
    assert len(cities) > 0
    kinds = {c["kind"] for c in cities}
    # At minimum we expect mcp + skill + persona to be present
    assert "mcp" in kinds, f"expected mcp tools, got {kinds}"
    assert "skill" in kinds, f"expected skills, got {kinds}"
    assert "persona" in kinds, f"expected personas, got {kinds}"


def test_cities_default_mode_is_capabilities():
    r = client.get("/api/cities")
    assert r.status_code == 200
    assert r.json()["mode"] == "capabilities"


def test_cities_entities_returns_entity_types():
    r = client.get("/api/cities?mode=entities")
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "entities"
    cities = data["cities"]
    assert len(cities) > 0
    assert all(c["kind"] == "entity_type" for c in cities)
    labels = {c["label"] for c in cities}
    assert "Person" in labels
    assert "Money" in labels
    assert "Decision" in labels


def test_cities_each_has_required_fields():
    r = client.get("/api/cities?mode=capabilities")
    cities = r.json()["cities"]
    for city in cities:
        assert "id" in city, f"missing id: {city}"
        assert "kind" in city, f"missing kind: {city}"
        assert "label" in city, f"missing label: {city}"


def test_cities_validators_classified():
    """Skills with 'validator' / 'checker' / 'guardian' / 'screen' in name → validator kind."""
    r = client.get("/api/cities?mode=capabilities")
    cities = r.json()["cities"]
    validator_cities = [c for c in cities if c["kind"] == "validator"]
    # We have brand-guardian, betrvg-checker, budget-checker etc. in the skills dir
    # so at least one should be classified as a validator.
    assert len(validator_cities) > 0, f"expected at least 1 validator, got 0 of {len(cities)} cities"


def test_cities_affinity_returns_pairs():
    r = client.get("/api/cities/affinity")
    assert r.status_code == 200
    data = r.json()
    assert "pairs" in data
    assert isinstance(data["pairs"], list)
    # Pairs may be empty if no events have fired yet — that's fine.


def test_entity_edges_returns_canonical():
    r = client.get("/api/cities/edges")
    assert r.status_code == 200
    data = r.json()
    assert "edges" in data
    assert len(data["edges"]) > 0
    # Each edge has from_kind / to_kind / label
    for e in data["edges"]:
        assert "from_kind" in e
        assert "to_kind" in e
        assert "label" in e
    # Real Kuzu rels derived from _REL_TABLES (post entity-view migration).
    pairs = {(e["from_kind"], e["to_kind"]) for e in data["edges"]}
    assert ("Person", "Organisation") in pairs
    assert ("Money", "Period") in pairs
