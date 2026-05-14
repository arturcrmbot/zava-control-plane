"""Pitch-i5: trend_cadence_watcher spawns workflows on KPI slope.

Drives the watcher with deterministic synthetic series injected
straight into the kpi_trend_buffer so the slope computation is
predictable. Verifies:

  * downward trend on win_rate fires the new-business pipeline scrub
  * (kpi, hour) is idempotent within an hour
  * flat trend → no spawn
  * reverse-direction trend → no spawn
  * trend.fired FleetEvent is emitted on the bus
"""
from __future__ import annotations

import asyncio
from collections import deque
from time import time
from typing import Any

import pytest

from api.server.services import kpi_trend_buffer
from api.server.services.ambient_agents import trend_cadence_watcher
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _seed_series(kpi_id: str, values: list[float], *, spacing_s: float = 60.0) -> None:
    """Inject a back-dated linear-ish series into the ring buffer.

    Newest sample lands at "now", older samples at -spacing_s steps.
    """
    now = time()
    n = len(values)
    series: deque = deque(maxlen=kpi_trend_buffer._MAX)
    for i, v in enumerate(values):
        ts = now - (n - 1 - i) * spacing_s
        series.append((ts, float(v)))
    kpi_trend_buffer._BUF[kpi_id] = series


def _make_watcher(
    *,
    kpi_values: dict[str, float] | None = None,
    hour: int = 10,
):
    """Build a watcher with stub spawn + capture lists.

    ``kpi_values`` is what ``_kpi_provider`` returns each tick; pass
    ``{}`` to leave the seeded buffer untouched.
    """
    spawned: list[str] = []

    async def _spawn(workflow_type: str) -> str:
        spawned.append(workflow_type)
        return f"WF-{workflow_type}"

    def _provider() -> dict[str, float]:
        return dict(kpi_values or {})

    bus = EventBus()
    captured: list[FleetEvent] = []
    bus.on_any(lambda e: captured.append(e))

    watcher = trend_cadence_watcher.TrendCadenceWatcher(
        bus=bus,
        kpi_provider=_provider,
        spawn_fn=_spawn,
        hour_provider=lambda: hour,
    )
    return watcher, bus, spawned, captured


@pytest.fixture(autouse=True)
def _clean_state():
    kpi_trend_buffer._reset_for_tests()
    trend_cadence_watcher._reset_for_tests()
    yield
    kpi_trend_buffer._reset_for_tests()
    trend_cadence_watcher._reset_for_tests()


# ----------------------------------------------------------------------
# tests
# ----------------------------------------------------------------------

def test_downward_win_rate_trend_spawns_pipeline_scrub():
    # Drop ~2 percentage points per minute over 7 minutes — well past
    # the win_rate_pct down threshold (-1.0/min).
    _seed_series("win_rate_pct", [60.0, 58.0, 56.0, 54.0, 52.0, 50.0, 48.0])

    watcher, _bus, spawned, captured = _make_watcher(kpi_values={})
    fired = asyncio.run(watcher.tick())

    assert ("win_rate_pct", "new-business-pipeline-scrub") in fired
    assert "new-business-pipeline-scrub" in spawned, (
        f"expected scrub spawn; got spawned={spawned} fired={fired}"
    )
    trend_events = [e for e in captured if e.type == "trend.fired"]
    assert len(trend_events) == 1
    payload: dict[str, Any] = trend_events[0].model_dump()
    assert payload["kpi_id"] == "win_rate_pct"
    assert payload["direction"] == "down"
    assert payload["workflow_type"] == "new-business-pipeline-scrub"
    assert payload["slope_per_minute"] < -1.0


def test_idempotent_per_kpi_per_hour():
    _seed_series("win_rate_pct", [60.0, 58.0, 56.0, 54.0, 52.0, 50.0, 48.0])

    watcher, _bus, spawned, _captured = _make_watcher(kpi_values={}, hour=10)

    asyncio.run(watcher.tick())
    asyncio.run(watcher.tick())
    asyncio.run(watcher.tick())

    pipeline_spawns = [w for w in spawned if w == "new-business-pipeline-scrub"]
    assert len(pipeline_spawns) == 1, (
        f"same (kpi, hour) must spawn once; got {pipeline_spawns}"
    )


def test_new_hour_fires_again():
    _seed_series("win_rate_pct", [60.0, 58.0, 56.0, 54.0, 52.0, 50.0, 48.0])

    watcher, _bus, spawned, _captured = _make_watcher(kpi_values={}, hour=10)
    asyncio.run(watcher.tick())
    assert spawned == ["new-business-pipeline-scrub"]

    # Roll the clock to a new hour — same trend, fresh fire.
    watcher._hour_provider = lambda: 11
    asyncio.run(watcher.tick())
    assert spawned == [
        "new-business-pipeline-scrub",
        "new-business-pipeline-scrub",
    ]


def test_flat_trend_does_not_spawn():
    _seed_series("win_rate_pct", [60.0] * 7)

    watcher, _bus, spawned, captured = _make_watcher(kpi_values={})
    asyncio.run(watcher.tick())

    assert spawned == []
    assert [e for e in captured if e.type == "trend.fired"] == []


def test_reverse_direction_does_not_spawn():
    # Rule for win_rate_pct is "down" with threshold -1.0/min.
    # An UPWARD slope (+2/min) is the opposite sign — must NOT fire.
    _seed_series("win_rate_pct", [40.0, 42.0, 44.0, 46.0, 48.0, 50.0, 52.0])

    watcher, _bus, spawned, captured = _make_watcher(kpi_values={})
    asyncio.run(watcher.tick())

    assert spawned == []
    assert [e for e in captured if e.type == "trend.fired"] == []


def test_upward_billable_utilisation_spawns_redeployment():
    _seed_series(
        "billable_utilisation_pct",
        [70.0, 72.0, 74.0, 76.0, 78.0, 80.0, 82.0],
    )

    watcher, _bus, spawned, _captured = _make_watcher(kpi_values={})
    fired = asyncio.run(watcher.tick())

    assert ("billable_utilisation_pct", "talent-redeployment") in fired
    assert "talent-redeployment" in spawned


def test_tick_records_provider_values():
    # When the provider returns fresh values they must land in the buffer
    # so subsequent ticks can compute slopes off the live stream.
    watcher, _bus, _spawned, _captured = _make_watcher(
        kpi_values={"win_rate_pct": 55.0},
    )
    asyncio.run(watcher.tick())

    last = kpi_trend_buffer.latest("win_rate_pct")
    assert last is not None
    assert last[1] == 55.0
