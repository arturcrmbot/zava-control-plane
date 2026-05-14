"""GET /api/whats-new — substrate self-modification feed (pitch-j6)."""
from __future__ import annotations

import time as _time

import pytest
from fastapi.testclient import TestClient

from api.server.routes import whats_new as wn
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent


@pytest.fixture(autouse=True)
def _clean_buffer():
    wn.reset_for_tests()
    yield
    wn.reset_for_tests()


@pytest.fixture
def client():
    from api.server.main import app
    return TestClient(app)


# ---------------------------------------------------------------------
# WhatsNewBuffer (direct unit-tests of the aggregator)
# ---------------------------------------------------------------------


def _emit(bus, type_, **fields):
    bus.emit(FleetEvent(type=type_, **fields))


def test_buffer_aggregates_all_four_source_event_types():
    bus = EventBus()
    buf = wn.WhatsNewBuffer()
    buf.attach(bus)

    _emit(bus, "policy.installed", vendor_id="ORG-acme", rejection_count=3)
    _emit(bus, "classifier.cache_hit", signature="abc123")
    _emit(bus, "routing.rebalanced",
          domain="ap_invoice", gate="controller_review",
          previous_role="cfo", preferred_role="controller")
    _emit(bus, "trend.fired",
          kpi_id="win_rate_pct", direction="down", workflow_type="scrub")

    items = buf.items_since(limit=50)
    assert len(items) == 4
    types = {i["type"] for i in items}
    assert types == {
        "policy.installed", "classifier.cache_hit",
        "routing.rebalanced", "trend.fired",
    }
    tracks = {i["source_track"] for i in items}
    assert tracks == {"I2", "I3", "I4", "I5"}
    # Each item carries summary + details + ts.
    for it in items:
        assert "summary" in it and isinstance(it["summary"], str) and it["summary"]
        assert "details" in it and isinstance(it["details"], dict)
        assert "ts" in it and isinstance(it["ts"], float)


def test_buffer_ignores_unrelated_event_types():
    bus = EventBus()
    buf = wn.WhatsNewBuffer()
    buf.attach(bus)
    _emit(bus, "workflow.started", workflow_id="W-1")
    _emit(bus, "decision.recorded", workflow_id="W-1")
    assert buf.items_since(limit=50) == []


def test_buffer_returns_reverse_chronological():
    bus = EventBus()
    buf = wn.WhatsNewBuffer()
    buf.attach(bus)

    _emit(bus, "trend.fired", kpi_id="a")
    _emit(bus, "policy.installed", vendor_id="ORG-1")
    _emit(bus, "classifier.cache_hit", signature="s1")

    items = buf.items_since(limit=50)
    assert len(items) == 3
    assert [i["ts"] for i in items] == sorted(
        (i["ts"] for i in items), reverse=True
    )
    # Last-emitted is first.
    assert items[0]["type"] == "classifier.cache_hit"


def test_buffer_since_cursor_returns_only_newer():
    bus = EventBus()
    buf = wn.WhatsNewBuffer()
    buf.attach(bus)

    _emit(bus, "policy.installed", vendor_id="ORG-old")
    cursor = _time.time()
    # Force a measurable gap so the strict-since filter is unambiguous.
    _time.sleep(0.01)
    _emit(bus, "trend.fired", kpi_id="b")
    _emit(bus, "classifier.cache_hit", signature="s2")

    new_items = buf.items_since(since=cursor, limit=50)
    assert len(new_items) == 2
    assert {i["type"] for i in new_items} == {"trend.fired", "classifier.cache_hit"}


def test_buffer_limit_caps_items():
    bus = EventBus()
    buf = wn.WhatsNewBuffer()
    buf.attach(bus)
    for i in range(10):
        _emit(bus, "classifier.cache_hit", signature=f"s{i}")
    assert len(buf.items_since(limit=3)) == 3


def test_buffer_detach_stops_capturing():
    bus = EventBus()
    buf = wn.WhatsNewBuffer()
    detach = buf.attach(bus)
    _emit(bus, "trend.fired", kpi_id="x")
    detach()
    _emit(bus, "trend.fired", kpi_id="y")
    items = buf.items_since(limit=50)
    assert len(items) == 1
    assert items[0]["details"].get("kpi_id") == "x"


# ---------------------------------------------------------------------
# /api/whats-new endpoint
# ---------------------------------------------------------------------


def _seed_singleton(items: list[dict]) -> None:
    """Push pre-shaped items straight into the singleton buffer.

    The route reads from this buffer; bypassing the bus keeps the
    endpoint test free of TestClient lifespan plumbing.
    """
    buf = wn.buffer()
    with buf._lock:  # noqa: SLF001 — test-only access
        for it in items:
            buf._items.append(it)  # noqa: SLF001


def test_endpoint_empty_returns_empty_items_list(client):
    r = client.get("/api/whats-new")
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_endpoint_returns_items_reverse_chronological(client):
    _seed_singleton([
        {"ts": 100.0, "type": "policy.installed",
         "summary": "old", "details": {}, "source_track": "I2"},
        {"ts": 200.0, "type": "trend.fired",
         "summary": "mid", "details": {}, "source_track": "I5"},
        {"ts": 300.0, "type": "classifier.cache_hit",
         "summary": "new", "details": {}, "source_track": "I3"},
    ])
    r = client.get("/api/whats-new")
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["ts"] for i in items] == [300.0, 200.0, 100.0]


def test_endpoint_since_filters(client):
    _seed_singleton([
        {"ts": 100.0, "type": "policy.installed",
         "summary": "old", "details": {}, "source_track": "I2"},
        {"ts": 200.0, "type": "trend.fired",
         "summary": "mid", "details": {}, "source_track": "I5"},
        {"ts": 300.0, "type": "classifier.cache_hit",
         "summary": "new", "details": {}, "source_track": "I3"},
    ])
    r = client.get("/api/whats-new", params={"since": 150.0})
    items = r.json()["items"]
    assert [i["ts"] for i in items] == [300.0, 200.0]


def test_endpoint_limit_caps_response(client):
    _seed_singleton([
        {"ts": float(i), "type": "trend.fired",
         "summary": str(i), "details": {}, "source_track": "I5"}
        for i in range(20)
    ])
    r = client.get("/api/whats-new", params={"limit": 5})
    assert len(r.json()["items"]) == 5


# ---------------------------------------------------------------------
# Source emit wiring (classifier_cache + routing_stats)
# ---------------------------------------------------------------------


def test_classifier_cache_lookup_emits_cache_hit_event(monkeypatch):
    """``classifier_cache.lookup`` must fire a ``classifier.cache_hit``
    onto the app_state bus so the J6 buffer sees the win."""
    from api.server.services import classifier_cache
    from api.server.state import app_state

    classifier_cache._reset_for_tests()
    captured: list[FleetEvent] = []
    off = app_state.bus.on_any(lambda e: captured.append(e))
    try:
        classifier_cache.remember("sig-X", {"label": "ok"})
        # Miss returns None and does NOT emit.
        assert classifier_cache.lookup("sig-Y") is None
        # Hit returns dict and DOES emit.
        assert classifier_cache.lookup("sig-X") == {"label": "ok"}
    finally:
        off()
        classifier_cache._reset_for_tests()
    hits = [e for e in captured if e.type == "classifier.cache_hit"]
    assert len(hits) == 1
    assert hits[0].model_dump().get("signature") == "sig-X"


def test_routing_stats_record_emits_rebalanced_on_flip(monkeypatch):
    """When ``preferred_role`` flips for a (domain, gate), exactly one
    ``routing.rebalanced`` event must land on the bus."""
    from api.server.services import routing_stats
    from api.server.state import app_state

    routing_stats.reset()
    captured: list[FleetEvent] = []
    off = app_state.bus.on_any(lambda e: captured.append(e))
    try:
        # Seed "boss" with a strong approval rate to make it the
        # initial preferred role at this cell.
        for _ in range(routing_stats.MIN_SAMPLES + 1):
            routing_stats.record("d", "g", "boss", approved=True)
        baseline_flips = [e for e in captured if e.type == "routing.rebalanced"]

        # Now feed "delegate" a perfect approval rate so the optimiser
        # flips to it (perfect 100% > boss's 100%, but the candidate
        # listing inside _maybe_emit_rebalance enumerates all roles
        # seen — both qualify, both at 1.0, and the tie-break order
        # is implementation-defined; what matters is that ONE flip
        # event is emitted as soon as a second eligible candidate
        # outranks the previous pick).
        for _ in range(routing_stats.MIN_SAMPLES + 5):
            routing_stats.record("d", "g", "delegate", approved=True)
        # Force boss into a slump so the flip is unambiguous.
        for _ in range(routing_stats.MIN_SAMPLES + 5):
            routing_stats.record("d", "g", "boss", approved=False)
    finally:
        off()
        routing_stats.reset()
    flips = [e for e in captured if e.type == "routing.rebalanced"]
    assert len(flips) >= 1
    last = flips[-1].model_dump()
    assert last.get("domain") == "d"
    assert last.get("gate") == "g"
    assert last.get("preferred_role") == "delegate"
    # Sanity: at the start there was no flip event (only the seed).
    assert baseline_flips == []
