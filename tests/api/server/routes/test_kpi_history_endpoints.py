"""Pitch-j1/j2/j3: HTTP endpoints reading the KPI history series.

Covers:
  * GET /api/kpis/history?kpi=...&window=... (j1)
  * GET /api/personas/{role}/history?metric=... (j2 — added in J2 commit)
  * GET /api/kpis/decision-latency?domain=... (j3 — added in J3 commit)

Each test isolates the SQLite ring under tmp_path via
``kpi_history.set_db_path`` so the production data file is never
touched.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server.services import kpi_history


@pytest.fixture
def isolated_db(tmp_path: Path):
    db = tmp_path / "kh.sqlite"
    kpi_history.set_db_path(db)
    kpi_history.init()
    yield db
    kpi_history.set_db_path(kpi_history._DEFAULT_DB_PATH)


@pytest.fixture
def client(isolated_db):
    from api.server.main import app
    return TestClient(app)


# ----------------------------------------------------------------------
# J1 — GET /api/kpis/history
# ----------------------------------------------------------------------

def test_history_endpoint_returns_recorded_samples(client):
    kpi_history.record("win_rate_pct", 50.0)
    kpi_history.record("win_rate_pct", 51.0)
    r = client.get("/api/kpis/history?kpi=win_rate_pct&window=60m")
    assert r.status_code == 200
    body = r.json()
    assert body["kpi"] == "win_rate_pct"
    assert body["window_seconds"] == 3600
    values = [p["value"] for p in body["points"]]
    assert values == [50.0, 51.0]


def test_history_endpoint_window_filters_out_old_samples(client, monkeypatch):
    now = time.time()
    monkeypatch.setattr(kpi_history.time, "time", lambda: now - 7200)
    kpi_history.record("k", 1.0)
    monkeypatch.setattr(kpi_history.time, "time", lambda: now)
    kpi_history.record("k", 2.0)
    r = client.get("/api/kpis/history?kpi=k&window=60m")
    assert r.status_code == 200
    assert [p["value"] for p in r.json()["points"]] == [2.0]


def test_history_endpoint_missing_kpi_returns_400(client):
    r = client.get("/api/kpis/history?kpi=")
    assert r.status_code == 400


def test_history_endpoint_unknown_kpi_returns_empty(client):
    r = client.get("/api/kpis/history?kpi=does-not-exist")
    assert r.status_code == 200
    assert r.json()["points"] == []


def test_history_endpoint_supports_dim_namespacing(client):
    kpi_history.record("persona_queue_depth", 4.0, dim="cfo")
    kpi_history.record("persona_queue_depth", 9.0, dim="hr_director")
    r = client.get(
        "/api/kpis/history?kpi=persona_queue_depth&window=60m&dim=cfo"
    )
    assert r.status_code == 200
    assert [p["value"] for p in r.json()["points"]] == [4.0]


# ----------------------------------------------------------------------
# J2 — GET /api/personas/{role}/history
# ----------------------------------------------------------------------

def test_persona_history_returns_queue_depth_series(client):
    kpi_history.record("persona_queue_depth", 1.0, dim="cfo")
    kpi_history.record("persona_queue_depth", 2.0, dim="cfo")
    kpi_history.record("persona_queue_depth", 99.0, dim="hr_director")
    r = client.get("/api/personas/cfo/history?metric=queue_depth&window=60m")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cfo"
    assert body["metric"] == "queue_depth"
    assert [p["value"] for p in body["points"]] == [1.0, 2.0]


def test_persona_history_returns_decisions_per_min_series(client):
    kpi_history.record("persona_decisions_per_min", 7.0, dim="cfo")
    r = client.get(
        "/api/personas/cfo/history?metric=decisions_per_min&window=60m"
    )
    assert r.status_code == 200
    assert [p["value"] for p in r.json()["points"]] == [7.0]


def test_persona_history_unknown_metric_returns_400(client):
    r = client.get("/api/personas/cfo/history?metric=bogus")
    assert r.status_code == 400


def test_persona_history_does_not_shadow_get_persona(client):
    """Sanity: registering /{role}/history must not break GET /{role}."""
    r = client.get("/api/personas/__definitely_not_a_role__")
    # Either 404 (registered persona-registry rejection) or 200 — anything
    # except a 405/422 from the new history route swallowing the path.
    assert r.status_code in (200, 404)


# ----------------------------------------------------------------------
# J3 — GET /api/kpis/decision-latency
# ----------------------------------------------------------------------

def test_decision_latency_endpoint_returns_series_and_mean(client):
    kpi_history.record("decision_latency_seconds", 10.0, dim="hiring")
    kpi_history.record("decision_latency_seconds", 20.0, dim="hiring")
    kpi_history.record("decision_latency_seconds", 99.0, dim="expense-claim")
    r = client.get("/api/kpis/decision-latency?domain=hiring&window=60m")
    assert r.status_code == 200
    body = r.json()
    assert body["domain"] == "hiring"
    assert body["window_seconds"] == 3600
    assert [p["value"] for p in body["points"]] == [10.0, 20.0]
    assert body["mean_seconds"] == pytest.approx(15.0)


def test_decision_latency_endpoint_empty_domain_returns_400(client):
    r = client.get("/api/kpis/decision-latency?domain=")
    assert r.status_code == 400


def test_decision_latency_endpoint_unknown_domain_returns_empty_with_null_mean(
    client,
):
    r = client.get("/api/kpis/decision-latency?domain=does-not-exist")
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == []
    assert body["mean_seconds"] is None
