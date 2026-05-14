"""Tests for the Phase 4 IP2 KpiStore."""
from __future__ import annotations

from pathlib import Path

from api.server.services.kpi_store import KpiStore


def test_publish_and_query_round_trip(tmp_path: Path):
    store = KpiStore(tmp_path / "kpis.sqlite")
    store.publish("finance", "dso", 41.2, "2026-04", schema_version=1)
    store.publish("finance", "dso", 39.7, "2026-05", schema_version=1)
    store.publish("hr", "time-to-hire", 38.0, "2026-05", schema_version=1)

    rows = store.query(function="finance", metric="dso")
    assert len(rows) == 2
    assert {r["period"] for r in rows} == {"2026-04", "2026-05"}
    assert all(r["function"] == "finance" for r in rows)


def test_query_filters_by_since(tmp_path: Path):
    store = KpiStore(tmp_path / "kpis.sqlite")
    store.publish("finance", "dso", 41.0, "2026-03", schema_version=1)
    store.publish("finance", "dso", 39.0, "2026-05", schema_version=1)
    rows = store.query(function="finance", metric="dso", since="2026-04")
    assert len(rows) == 1
    assert rows[0]["period"] == "2026-05"


def test_schema_version_tolerance(tmp_path: Path):
    """Two snapshots with different schema_versions are both queryable
    (DEC-OQ3) — readers see the union and project missing keys at the
    aggregation layer."""
    store = KpiStore(tmp_path / "kpis.sqlite")
    store.publish("finance", "dso", 41.0, "2026-04", schema_version=1)
    store.publish("finance", "dso", 38.0, "2026-05", schema_version=2)
    rows = store.query(function="finance", metric="dso")
    versions = {r["schema_version"] for r in rows}
    assert versions == {1, 2}


def test_query_no_filter_returns_all(tmp_path: Path):
    store = KpiStore(tmp_path / "kpis.sqlite")
    store.publish("finance", "dso", 1.0, "2026-05")
    store.publish("hr", "time-to-hire", 2.0, "2026-05")
    rows = store.query()
    assert len(rows) == 2
