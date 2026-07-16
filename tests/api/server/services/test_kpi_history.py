"""Pitch-j1: durable KPI history SQLite ring.

Covers the full public surface (init / record / series / latest /
cleanup_old) on a tmp-path DB so the production data file is never
touched. ``set_db_path`` is the test-only knob; every test re-points
it inside its own tmp_path.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from api.server.services import kpi_history


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path):
    original = kpi_history._DB_PATH
    db = tmp_path / "kh.sqlite"
    kpi_history.set_db_path(db)
    kpi_history.init()
    yield db
    kpi_history.set_db_path(original)


def test_empty_series_and_latest_return_empty():
    assert kpi_history.series("missing") == []
    assert kpi_history.latest("missing") is None


def test_record_then_latest_roundtrip():
    kpi_history.record("win_rate_pct", 42.0)
    got = kpi_history.latest("win_rate_pct")
    assert got is not None
    ts, value = got
    assert value == pytest.approx(42.0)
    assert ts <= time.time() + 1.0


def test_record_with_dim_namespaces_correctly():
    kpi_history.record("persona_queue_depth", 3.0, dim="hr_director")
    kpi_history.record("persona_queue_depth", 7.0, dim="cfo")
    assert kpi_history.latest("persona_queue_depth", dim="hr_director")[1] == 3.0
    assert kpi_history.latest("persona_queue_depth", dim="cfo")[1] == 7.0
    # Un-dimmed query should not see the dimensioned rows.
    assert kpi_history.latest("persona_queue_depth") is None


def test_series_window_filters_out_old_samples(monkeypatch):
    now = time.time()
    # Insert one row "two hours ago" by patching time.time during record.
    monkeypatch.setattr(kpi_history.time, "time", lambda: now - 7200)
    kpi_history.record("k", 1.0)
    monkeypatch.setattr(kpi_history.time, "time", lambda: now)
    kpi_history.record("k", 2.0)
    pts = kpi_history.series("k", since_seconds=3600)
    assert [v for _t, v in pts] == [2.0]


def test_series_returns_chronological_order():
    for v in (1.0, 2.0, 3.0):
        kpi_history.record("k", v)
        time.sleep(0.001)
    pts = kpi_history.series("k", since_seconds=3600)
    timestamps = [t for t, _v in pts]
    assert timestamps == sorted(timestamps)
    assert [v for _t, v in pts] == [1.0, 2.0, 3.0]


def test_cleanup_old_drops_rows_past_retention(monkeypatch):
    now = time.time()
    monkeypatch.setattr(
        kpi_history.time, "time", lambda: now - kpi_history._RETENTION - 100
    )
    kpi_history.record("k", 99.0)
    monkeypatch.setattr(kpi_history.time, "time", lambda: now)
    kpi_history.record("k", 1.0)
    kpi_history.cleanup_old()
    pts = kpi_history.series("k", since_seconds=kpi_history._RETENTION + 1000)
    assert [v for _t, v in pts] == [1.0]


def test_record_coerces_value_to_float():
    kpi_history.record("k", 5)  # int → float
    assert kpi_history.latest("k")[1] == 5.0


def test_record_non_numeric_raises():
    with pytest.raises((TypeError, ValueError)):
        kpi_history.record("k", "not-a-number")


def test_init_is_idempotent():
    # Calling init() twice must not error or wipe state.
    kpi_history.record("k", 1.0)
    kpi_history.init()
    kpi_history.init()
    assert kpi_history.latest("k") is not None


def test_kpi_trend_buffer_record_forwards_into_history():
    """I5's in-memory ring still works AND now forwards into the durable store."""
    from api.server.services import kpi_trend_buffer

    kpi_trend_buffer._reset_for_tests()
    kpi_trend_buffer.record("forwarded_kpi", 11.0)
    # In-memory ring still has it (back-compat contract).
    assert kpi_trend_buffer.latest("forwarded_kpi") is not None
    # And the durable store does too.
    got = kpi_history.latest("forwarded_kpi")
    assert got is not None
    assert got[1] == 11.0
