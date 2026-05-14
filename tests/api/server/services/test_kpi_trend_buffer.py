"""Pitch-i5: provisional KPI trend ring buffer.

Covers the public surface the trend-cadence watcher relies on:
empty-buffer + insufficient-sample slope guards, deterministic slope
on a hand-built linear series, and ring eviction past ``_MAX``.
"""
from __future__ import annotations

import math
from collections import deque
from time import time

import pytest

from api.server.services import kpi_trend_buffer


@pytest.fixture(autouse=True)
def _clean_buffer():
    kpi_trend_buffer._reset_for_tests()
    yield
    kpi_trend_buffer._reset_for_tests()


def test_empty_buffer_slope_is_none():
    assert kpi_trend_buffer.slope("missing", window_seconds=60) is None
    assert kpi_trend_buffer.latest("missing") is None


def test_fewer_than_three_samples_slope_is_none():
    kpi_trend_buffer.record("k", 1.0)
    kpi_trend_buffer.record("k", 2.0)
    assert kpi_trend_buffer.slope("k", window_seconds=3600) is None


def test_deterministic_slope_on_handbuilt_series():
    # Inject a perfect line: value = 2 * t (offset removed) over five
    # in-window samples. Bypass record() so timestamps are deterministic.
    now = time()
    series = deque(maxlen=kpi_trend_buffer._MAX)
    # t = 0, 10, 20, 30, 40 seconds in the past relative to now;
    # value = 100, 120, 140, 160, 180  →  slope = 2 value-units/second.
    for i, value in enumerate((100.0, 120.0, 140.0, 160.0, 180.0)):
        series.append((now - (40 - i * 10), value))
    kpi_trend_buffer._BUF["k"] = series

    s = kpi_trend_buffer.slope("k", window_seconds=120)
    assert s is not None
    assert math.isclose(s, 2.0, rel_tol=1e-9, abs_tol=1e-9), f"got {s}"

    # latest() returns the most recent (timestamp, value) pair.
    last = kpi_trend_buffer.latest("k")
    assert last is not None
    assert math.isclose(last[1], 180.0)


def test_window_excludes_old_samples():
    now = time()
    series = deque(maxlen=kpi_trend_buffer._MAX)
    # Two ancient samples (well outside the 60s window) plus three
    # fresh ones at t-2, t-1, t.
    series.append((now - 10_000, 1.0))
    series.append((now - 9_999, 2.0))
    series.append((now - 2, 50.0))
    series.append((now - 1, 60.0))
    series.append((now,     70.0))
    kpi_trend_buffer._BUF["k"] = series

    s = kpi_trend_buffer.slope("k", window_seconds=60)
    # In-window points are essentially y=10x+offset → slope ≈ 10/sec.
    assert s is not None
    assert s > 0


def test_ring_evicts_oldest_past_max():
    cap = kpi_trend_buffer._MAX
    for i in range(cap + 5):
        kpi_trend_buffer.record("k", float(i))
    buf = kpi_trend_buffer._BUF["k"]
    assert len(buf) == cap, f"expected ring to cap at {cap}; got {len(buf)}"
    # Oldest surviving sample is the 6th insert (value == 5.0).
    assert buf[0][1] == 5.0
    assert buf[-1][1] == float(cap + 4)


def test_record_coerces_numeric_strings_or_raises():
    kpi_trend_buffer.record("k", 3)
    last = kpi_trend_buffer.latest("k")
    assert last is not None and last[1] == 3.0
    with pytest.raises((TypeError, ValueError)):
        kpi_trend_buffer.record("k", "not-a-number")
