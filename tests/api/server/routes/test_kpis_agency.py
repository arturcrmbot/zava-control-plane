"""GET /api/kpis/agency — agency KPIs for the cosmic HUD (pitch-e4)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite

from tests.api.server.routes._entities_fixtures import client, graph  # noqa: F401


_EXPECTED_KPI_IDS = {
    "win_rate_pct",
    "billable_utilisation_pct",
    "gross_profit_per_brand",
    "client_churn_30d",
    "time_to_launch_days",
    "freelancer_mix_pct",
    "intercompany_recharge_volume",
    "pitch_cost",
}


def _kpis_by_id(body: dict) -> dict[str, dict]:
    return {k["id"]: k for k in body["kpis"]}


def test_agency_kpis_endpoint_returns_200(graph, client):
    r = client.get("/api/kpis/agency")
    assert r.status_code == 200


def test_agency_kpis_all_eight_present(graph, client):
    r = client.get("/api/kpis/agency")
    body = r.json()
    assert {k["id"] for k in body["kpis"]} == _EXPECTED_KPI_IDS
    assert len(body["kpis"]) == 8


def test_agency_kpis_unavailable_have_null_value_and_reason(graph, client):
    # Empty graph: win_rate, time_to_launch, freelancer_mix, gross_profit_per_brand
    # all have nothing to compute against.
    r = client.get("/api/kpis/agency")
    by_id = _kpis_by_id(r.json())
    for kid in (
        "win_rate_pct", "time_to_launch_days",
        "freelancer_mix_pct", "gross_profit_per_brand",
    ):
        kpi = by_id[kid]
        assert kpi["value"] is None, f"{kid} should be null on empty graph: {kpi}"
        assert kpi["unavailable_reason"], f"{kid} must carry an unavailable_reason"


def test_agency_kpis_freelancer_mix_under_100(graph, client):
    # 3 people, 1 freelance — mix should be 33.3, well under 100.
    graph.upsert(EntityWrite(kind="Person", id="P1", attrs={"name": "A", "department": "creative"}))
    graph.upsert(EntityWrite(kind="Person", id="P2", attrs={"name": "B", "department": "freelance"}))
    graph.upsert(EntityWrite(kind="Person", id="P3", attrs={"name": "C", "department": "creative"}))
    r = client.get("/api/kpis/agency")
    by_id = _kpis_by_id(r.json())
    val = by_id["freelancer_mix_pct"]["value"]
    assert val is not None
    assert 0 <= val < 100, f"freelancer_mix_pct must be in [0, 100): {val}"


def test_agency_kpis_numeric_values_non_negative(graph, client):
    graph.upsert(EntityWrite(kind="Money", id="M1", attrs={"amount": 1000.0, "kind": "recharge"}))
    graph.upsert(EntityWrite(kind="Money", id="M2", attrs={"amount": 500.0, "kind": "pitch_cost"}))
    r = client.get("/api/kpis/agency")
    by_id = _kpis_by_id(r.json())
    for kid in (
        "billable_utilisation_pct", "client_churn_30d",
        "intercompany_recharge_volume", "pitch_cost",
    ):
        kpi = by_id[kid]
        assert kpi["value"] is not None, f"{kid} should be numeric: {kpi}"
        assert isinstance(kpi["value"], (int, float))
        assert kpi["value"] >= 0, f"{kid} must be non-negative: {kpi['value']}"


def test_agency_kpis_recharge_volume_sums(graph, client):
    graph.upsert(EntityWrite(kind="Money", id="R1", attrs={"amount": 100.0, "kind": "recharge"}))
    graph.upsert(EntityWrite(kind="Money", id="R2", attrs={"amount": 250.5, "kind": "recharge"}))
    graph.upsert(EntityWrite(kind="Money", id="R3", attrs={"amount": 999.0, "kind": "fee"}))
    r = client.get("/api/kpis/agency")
    by_id = _kpis_by_id(r.json())
    assert by_id["intercompany_recharge_volume"]["value"] == 350.5


def test_agency_kpis_response_shape(graph, client):
    r = client.get("/api/kpis/agency")
    body = r.json()
    for kpi in body["kpis"]:
        assert set(kpi.keys()) == {"id", "label", "value", "unit", "unavailable_reason"}
        assert isinstance(kpi["id"], str)
        assert isinstance(kpi["label"], str)
