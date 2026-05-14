"""Phase 2 — /api/accounts/summary route."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.server.main import app
from api.server.state import app_state
from tests.api.server.fixtures.entity_graph_seed import seed_account_demo
from tests.api.server.routes._accounts_fixtures import client_with_seed  # noqa: F401


def test_accounts_summary_returns_per_account_totals(client_with_seed):
    r = client_with_seed.get("/api/accounts/summary")
    assert r.status_code == 200
    data = r.json()
    assert "accounts" in data
    rows = {a["id"]: a for a in data["accounts"]}
    assert "ACC-6010" in rows
    assert rows["ACC-6010"]["total_gbp"] > 0
    assert rows["ACC-6010"]["row_count"] >= 1


def test_accounts_summary_groups_by_period(client_with_seed):
    r = client_with_seed.get("/api/accounts/summary?group_by=period")
    assert r.status_code == 200
    assert "by_period" in r.json()


def test_accounts_summary_filters_by_subsidiary(client_with_seed):
    r = client_with_seed.get(
        "/api/accounts/summary?cost_centre=CC-zava-creative"
    )
    assert r.status_code == 200
    # Every returned account row must trace to CC-zava-creative
    for a in r.json()["accounts"]:
        assert "CC-zava-creative" in a.get("cost_centres", [])


def test_accounts_by_brand_returns_per_brand_totals(client_with_seed):
    r = client_with_seed.get("/api/accounts/by-brand")
    assert r.status_code == 200
    data = r.json()
    assert "brands" in data
    rows = {b["brand_id"]: b for b in data["brands"]}
    assert "BRAND-aurora" in rows
    assert rows["BRAND-aurora"]["total_gbp"] > 0
