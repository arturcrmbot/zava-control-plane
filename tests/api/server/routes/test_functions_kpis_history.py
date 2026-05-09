"""The Org Building (IP7, TASK-037) — kpis-latest ?history=N extension."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server.services.kpi_store import KpiStore


@pytest.fixture(scope="module")
def client():
    from api.server.main import app
    with TestClient(app) as c:
        yield c


def test_history_param_returns_history_key(client):
    r = client.get("/api/functions/finance/kpis-latest?history=30")
    assert r.status_code == 200
    body = r.json()
    assert "history" in body
    # Even with an empty store the structure is per-declared-metric.
    assert isinstance(body["history"], dict)


def test_history_zero_omits_history_key(client):
    r = client.get("/api/functions/finance/kpis-latest")
    assert r.status_code == 200
    body = r.json()
    assert "history" not in body


def test_history_truncates_to_n_per_metric(tmp_path: Path):
    """Direct unit test against KpiStore — ensures the truncation logic
    keeps the most-recent N rows per metric in oldest→newest order."""
    from api.server.routes.functions import function_kpis_latest
    from api.server.state import app_state

    store = KpiStore(tmp_path / "kpi-history.sqlite")
    for i in range(50):
        store.publish("finance", "dso", float(30 - i * 0.1), period=f"2025-{i:02d}")

    # Swap in our test store, call the route function directly, then
    # restore. (Avoids monkey-patching the FastAPI dep tree.)
    saved = getattr(app_state, "kpi_store", None)
    app_state.kpi_store = store
    try:
        body = function_kpis_latest("finance", history=10)
    finally:
        app_state.kpi_store = saved

    assert "history" in body
    dso_history = body["history"]["dso"]
    assert len(dso_history) == 10
    # Ascending captured_at order.
    captured = [row["captured_at"] for row in dso_history]
    assert captured == sorted(captured)
