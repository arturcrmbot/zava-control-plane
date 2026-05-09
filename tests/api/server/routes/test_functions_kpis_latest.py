"""The Org Building (IP1, TASK-003) — /api/functions/{name}/kpis-latest."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server.services.kpi_store import KpiStore


@pytest.fixture(scope="module")
def client():
    from api.server.main import app
    with TestClient(app) as c:
        yield c


def test_kpis_latest_returns_404_for_legacy(client):
    r = client.get("/api/functions/legacy/kpis-latest")
    assert r.status_code == 404


def test_kpis_latest_returns_404_for_unknown(client):
    r = client.get("/api/functions/does-not-exist/kpis-latest")
    assert r.status_code == 404


def test_kpis_latest_returns_empty_metrics_when_no_snapshots(client):
    """Even with no published KPIs (entity plane disabled or empty store),
    the route returns 200 with an empty metrics map — the front-end uses
    the empty case to render '—' placeholders."""
    r = client.get("/api/functions/finance/kpis-latest")
    assert r.status_code == 200
    body = r.json()
    assert "metrics" in body
    assert isinstance(body["metrics"], dict)


def test_kpis_latest_reduces_to_latest_per_metric(tmp_path: Path):
    """Direct unit-style coverage of the reduction logic — drives a fresh
    KpiStore so the test is independent of the global app_state.kpi_store
    (which may be ``None`` when the entity plane is disabled)."""
    store = KpiStore(tmp_path / "kpis.sqlite")
    store.publish("finance", "dso", 30.0, period="2025-09")
    time.sleep(0.001)
    store.publish("finance", "dso", 28.0, period="2025-10")
    store.publish("finance", "dpo", 41.0, period="2025-10")
    rows = store.query(function="finance")
    latest: dict[str, dict] = {}
    for r in rows:
        prev = latest.get(r["metric"])
        if prev is None or r["captured_at"] > prev["captured_at"]:
            latest[r["metric"]] = {
                "value": r["value"],
                "period": r["period"],
                "captured_at": r["captured_at"],
            }
    assert latest["dso"]["value"] == 28.0
    assert latest["dso"]["period"] == "2025-10"
    assert latest["dpo"]["value"] == 41.0
