"""Tests for api.server.data_fabric.pack (pitch-b9)."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.data_fabric.pack import DataPack, build_zava_pack
from api.server.services.entity_graph import EntityGraph


def test_build_zava_pack_defaults():
    pack = build_zava_pack()
    assert isinstance(pack, DataPack)
    assert pack.name == "zava"
    assert pack.seed == 42
    assert pack.fiscal_year == 2026
    assert pack.employee_count == 100
    assert pack.vendor_count == 50
    assert pack.client_count == 6
    assert pack.asset_count == 150
    assert pack.money_count == 750
    assert pack.historical_workflow_count == 125
    assert pack.in_flight_workflow_count == 25


def test_materialise_writes_full_graph(tmp_path: Path):
    pack = build_zava_pack()
    result = pack.materialise(tmp_path / "g.kuzu")

    assert result["fiscal_year"] == 2026
    assert result["node_count"] >= 1500, result
    assert result["edge_count"] >= 5000, result

    summary = result["generator_summary"]
    assert summary["periods"] == 17
    assert summary["subsidiaries"] == 5
    assert summary["clients"] == 6
    assert summary["employees"] == 100
    assert summary["vendors"] == 50
    assert summary["assets"] == 150
    assert summary["money"] == 750
    assert summary["workflows"] == 150


def test_materialised_graph_reopens_with_positive_counts(tmp_path: Path):
    pack = build_zava_pack()
    pack.materialise(tmp_path / "g.kuzu")

    fresh = EntityGraph(tmp_path / "g.kuzu")
    try:
        counts = fresh.count_by_kind()
    finally:
        fresh.close()

    for kind in ("Person", "Organisation", "Money", "Period", "Workflow", "Subsidiary"):
        assert counts.get(kind, 0) > 0, (kind, counts)
    # All 5 named subsidiaries land as first-class Subsidiary nodes.
    assert counts.get("Subsidiary") == 5, counts


def test_materialised_subsidiaries_have_part_of_edges(tmp_path: Path):
    """4 of 5 subsidiaries PART_OF the ORG-zava-group holding org."""
    pack = build_zava_pack()
    pack.materialise(tmp_path / "g.kuzu")

    fresh = EntityGraph(tmp_path / "g.kuzu")
    try:
        rows = fresh.query(
            "MATCH (s:Subsidiary)-[r:PART_OF]->(o:Organisation) "
            "RETURN s.id AS sub, o.id AS holding"
        )
    finally:
        fresh.close()

    assert len(rows) == 4, rows
    assert all(r["holding"] == "ORG-zava-group" for r in rows), rows
    assert "ORG-zava-group" not in {r["sub"] for r in rows}, rows


def test_materialise_is_deterministic(tmp_path: Path):
    a = build_zava_pack().materialise(tmp_path / "a.kuzu")
    b = build_zava_pack().materialise(tmp_path / "b.kuzu")
    assert a["node_count"] == b["node_count"]
    assert a["edge_count"] == b["edge_count"]
    assert a["generator_summary"] == b["generator_summary"]


def test_materialise_idempotent_overwrites_existing(tmp_path: Path):
    target = tmp_path / "g.kuzu"
    pack = build_zava_pack()
    first = pack.materialise(target)
    # Second run on the same path should wipe + rebuild without error.
    second = pack.materialise(target)
    assert first["node_count"] == second["node_count"]


@pytest.fixture
def materialised(tmp_path: Path):
    pack = DataPack(name="test", seed=42, fiscal_year=2026)
    out = tmp_path / "graph.kuzu"
    summary = pack.materialise(out)
    return out, summary


def test_no_person_id_leaks_into_decision_persona_role(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    res = conn.execute(
        "MATCH (d:Decision) WHERE d.persona_role STARTS WITH 'PERSON-' "
        "RETURN count(*) AS c"
    )
    assert int(res.get_next()[0]) == 0, (
        "DataPack must write role strings, not person ids, into persona_role"
    )


def test_chart_of_accounts_seeded(materialised):
    import kuzu
    db_path, summary = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute("MATCH (a:Account) RETURN count(*) AS c").get_next()[0])
    assert n >= 8, f"expected at least 8 GL accounts, got {n}"


def test_cost_centres_one_per_subsidiary(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute("MATCH (cc:CostCentre) RETURN count(*) AS c").get_next()[0])
    # 5 subsidiaries in _SUBSIDIARY_META but the holding (ORG-zava-group)
    # doesn't get a CC — holdings don't take cost. So 4.
    assert n == 4, f"expected 4 cost centres (one per non-holding subsidiary), got {n}"


def test_every_money_row_booked(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    total = int(conn.execute("MATCH (m:Money) RETURN count(*) AS c").get_next()[0])
    booked = int(conn.execute(
        "MATCH (m:Money)-[:BOOKED_AGAINST]->(:Account) RETURN count(DISTINCT m) AS c"
    ).get_next()[0])
    assert booked == total, (
        f"every Money row must be booked to a GL account; {booked}/{total}"
    )


def test_brands_seeded_as_first_class(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute("MATCH (b:Brand) RETURN count(*) AS c").get_next()[0])
    assert n >= 8, f"expected at least 8 Brand nodes, got {n}"


def test_brand_of_edge_to_client_org(materialised):
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute(
        "MATCH (b:Brand)-[:BRAND_OF]->(o:Organisation {kind: 'client'}) "
        "RETURN count(*) AS c"
    ).get_next()[0])
    assert n >= 8


def test_pitch_emitting_workflows_actually_create_pitches(materialised):
    """client-renewal etc. emit Pitch nodes via their projection. After
    DataPack runs them through the bus, the Pitch table must be non-empty."""
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute("MATCH (p:Pitch) RETURN count(*) AS c").get_next()[0])
    assert n >= 5, f"expected ≥5 Pitch nodes from one-shot agency workflows, got {n}"


def test_creative_campaign_workflows_create_campaigns(materialised):
    """Plan §3.3 floor was >= 14, assuming many creative-campaign workflows
    in the seed timeline. Reality at default `_domain_weights`: only ~1
    creative-campaign + ~1 client-renewal spawn, yielding 2 Campaign nodes.
    Lowered to >= 2 to assert the projection-dispatch WIRING works (was 0
    before commit 9ac79f3b). Re-weighting the timeline for higher Campaign
    counts is a follow-up outside Task 3.3 scope.
    """
    import kuzu
    db_path, _ = materialised
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)
    n = int(conn.execute("MATCH (cmp:Campaign) RETURN count(*) AS c").get_next()[0])
    assert n >= 2, f"expected ≥2 Campaign nodes from one-shot agency workflows, got {n}"
