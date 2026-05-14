"""Tests for api.server.data_fabric.workflow_timeline (pitch-b7)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from api.server.data_fabric.workflow_timeline import (
    TimelineEntry,
    generate_timeline,
)
from api.shared.domains import DOMAINS


_END = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)


def _live_workflow_types() -> set[str]:
    return {wt for wt, d in DOMAINS.items() if not d.stub}


def test_generate_timeline_counts_and_split():
    entries = generate_timeline(seed=42, end_time=_END, in_flight_count=25, historical_count=125)
    assert len(entries) == 150
    in_flight = [e for e in entries if not e.completed]
    completed = [e for e in entries if e.completed]
    assert len(in_flight) == 25
    assert len(completed) == 125
    for e in entries:
        assert isinstance(e, TimelineEntry)


def test_generate_timeline_at_least_one_per_live_domain():
    entries = generate_timeline(seed=1, end_time=_END)
    seen = {e.workflow.type for e in entries}
    live = _live_workflow_types()
    missing = live - seen
    assert not missing, f"missing live domains: {missing}"


def test_generate_timeline_workflow_ids_unique_and_prefixed():
    entries = generate_timeline(seed=3, end_time=_END)
    ids = [e.workflow.id for e in entries]
    assert len(ids) == len(set(ids))
    for e in entries:
        domain = DOMAINS[e.workflow.type]
        assert e.workflow.id.startswith(f"{domain.workflow_id_prefix}-"), e.workflow.id
        suffix = e.workflow.id[len(domain.workflow_id_prefix) + 1 :]
        assert suffix.isdigit() and len(suffix) >= 4


def test_generate_timeline_spawned_at_within_last_24h():
    entries = generate_timeline(seed=7, end_time=_END)
    earliest = _END - timedelta(hours=24)
    for e in entries:
        assert earliest <= e.spawned_at <= _END
        if e.completed:
            assert e.completed_at is not None
            assert e.completed_at >= e.spawned_at
            assert e.completed_at <= _END
        else:
            assert e.completed_at is None
            # in-flight window is the last 1-2 hours.
            assert e.spawned_at >= _END - timedelta(hours=2)
            assert e.spawned_at <= _END - timedelta(hours=1)


def test_generate_timeline_deterministic():
    a = generate_timeline(seed=99, end_time=_END)
    b = generate_timeline(seed=99, end_time=_END)
    assert [(e.workflow.id, e.completed, e.spawned_at) for e in a] == [
        (e.workflow.id, e.completed, e.spawned_at) for e in b
    ]
