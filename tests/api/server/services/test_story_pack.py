"""Pitch-j5 — render_story / write_hourly_story.

Drives the renderer with a stub audit ledger so the test doesn't need
the full :class:`AppState` constructed. Verifies markdown structure,
window filtering, and idempotency of ``write_hourly_story`` on the
(hour, hour+1) key.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from api.server.services import story_pack


@pytest.fixture
def fake_audit(monkeypatch):
    """Replace ``_safe_audit_entries`` with a controllable list."""
    rows: list[dict] = []
    monkeypatch.setattr(story_pack, "_safe_audit_entries", lambda: list(rows))
    return rows


def _entry(action: str, ts: float, **details) -> dict:
    return {"action": action, "timestamp": ts, "details": details}


def test_render_story_empty_window_renders_skeleton(fake_audit):
    md = story_pack.render_story(since_unix_ts=0.0, until_unix_ts=10.0)
    assert "# Story of the hour" in md
    assert "Top 10 events" in md
    assert "Biggest entity-graph deltas" in md
    assert "Learning-loop wins" in md
    # Skeleton placeholders for an empty window.
    assert "no events recorded in window" in md
    assert "no entity mutations in window" in md
    assert "no learning events in window" in md


def test_render_story_counts_top_events_and_deltas(fake_audit):
    base = 1_700_000_000.0
    fake_audit.extend([
        _entry("workflow.started", base + 1, workflow_id="w1"),
        _entry("workflow.started", base + 2, workflow_id="w2"),
        _entry("workflow.started", base + 3, workflow_id="w3"),
        _entry("workflow.resolved", base + 4, workflow_id="w1"),
        _entry("entity.upserted", base + 5, kind="Person", id="P1"),
        _entry("entity.upserted", base + 6, kind="Person", id="P2"),
        _entry("entity.upserted", base + 7, kind="Org", id="O1"),
        _entry("entity.linked", base + 8, src_id="P1", dst_id="O1", rel="WORKS_AT"),
        _entry("policy.installed", base + 9, vendor_id="ORG-x"),
        _entry("trend.fired", base + 10, kpi_id="win_rate_pct"),
        _entry("classifier.cache_hit", base + 11),
        _entry("classifier.cache_hit", base + 12),
        _entry("routing.rebalanced", base + 13, domain="d", gate="g"),
    ])
    md = story_pack.render_story(
        since_unix_ts=base,
        until_unix_ts=base + 100,
    )
    # Top events section must show the most-frequent action first.
    assert "**workflow.started** — 3" in md
    assert "**entity.upserted** — 3" in md
    # Entity-graph deltas: per-kind upserts + per-rel links.
    assert "upsert Person: 2" in md
    assert "upsert Org: 1" in md
    assert "link WORKS_AT: 1" in md
    # Learning wins with the labeled track id.
    assert "I2 auto-block rule installed: 1" in md
    assert "I3 classifier cache hit: 2" in md
    assert "I4 routing rebalance: 1" in md
    assert "I5 trend-driven cadence: 1" in md


def test_render_story_filters_window(fake_audit):
    fake_audit.extend([
        _entry("workflow.started", 100.0),       # before window — excluded
        _entry("workflow.started", 200.0),       # in window
        _entry("workflow.started", 300.0),       # in window
        _entry("workflow.started", 400.0),       # after window — excluded (until exclusive)
    ])
    md = story_pack.render_story(since_unix_ts=200.0, until_unix_ts=400.0)
    assert "**workflow.started** — 2" in md


def test_render_story_skips_entries_with_no_timestamp(fake_audit):
    fake_audit.extend([
        {"action": "workflow.started", "details": {}},  # no timestamp
        _entry("workflow.started", 200.0),
    ])
    md = story_pack.render_story(since_unix_ts=0.0, until_unix_ts=10_000.0)
    assert "**workflow.started** — 1" in md


def test_write_hourly_story_writes_to_expected_path(tmp_path: Path, fake_audit):
    fake_audit.extend([
        _entry("workflow.started", 1_700_000_000.0, workflow_id="w1"),
    ])
    # 2023-11-14T22:00 UTC
    now_ts = _dt.datetime(2023, 11, 14, 22, 30, tzinfo=_dt.timezone.utc).timestamp()
    path = story_pack.write_hourly_story(base_dir=tmp_path, now_ts=now_ts)
    # Hour floor of (now - 1h) → 21:00.
    assert path.name == "story-2023-11-14T21.md"
    assert path.parent == tmp_path
    assert path.exists()
    body = path.read_text(encoding="utf-8")
    assert "# Story of the hour" in body


def test_write_hourly_story_idempotent_on_hour(tmp_path: Path, fake_audit):
    now_ts = _dt.datetime(2023, 11, 14, 22, 30, tzinfo=_dt.timezone.utc).timestamp()
    p1 = story_pack.write_hourly_story(base_dir=tmp_path, now_ts=now_ts)
    p2 = story_pack.write_hourly_story(base_dir=tmp_path, now_ts=now_ts + 100)
    # Same hour ⇒ same path; only one file on disk.
    assert p1 == p2
    assert sorted(p.name for p in tmp_path.glob("story-*.md")) == [p1.name]


def test_write_hourly_story_creates_directory(tmp_path: Path, fake_audit):
    target = tmp_path / "nested" / "snapshots"
    assert not target.exists()
    path = story_pack.write_hourly_story(
        base_dir=target,
        now_ts=_dt.datetime(2023, 11, 14, 22, 30, tzinfo=_dt.timezone.utc).timestamp(),
    )
    assert target.is_dir()
    assert path.parent == target


def test_writer_tick_writes_once_per_hour(tmp_path: Path, fake_audit):
    from api.server.services.ambient_agents import story_pack_writer

    story_pack_writer._reset_for_tests()
    writer = story_pack_writer.StoryPackWriter(base_dir=tmp_path)

    base = _dt.datetime(2023, 11, 14, 22, 30, tzinfo=_dt.timezone.utc).timestamp()
    p1 = writer.tick(now_ts=base)
    assert p1 is not None
    # Same hour → no new write.
    p2 = writer.tick(now_ts=base + 60)
    assert p2 is None
    # Roll the clock to next hour → new write.
    next_hour = base + 3600
    p3 = writer.tick(now_ts=next_hour)
    assert p3 is not None
    assert p3 != p1
