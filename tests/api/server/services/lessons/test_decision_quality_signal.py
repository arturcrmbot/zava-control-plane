from datetime import datetime, timedelta, timezone

from api.server.services.lessons.decision_quality_signal import (
    should_trigger,
    TriggerInputs,
)


def test_fires_when_backlog_exceeds_threshold():
    inp = TriggerInputs(
        domain="hiring",
        unconsumed_backlog=35,
        last_pass_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        backlog_threshold=30,
        heartbeat_seconds=120,
        now=datetime.now(timezone.utc),
    )
    fired, reason = should_trigger(inp)
    assert fired is True
    assert "backlog" in reason


def test_fires_on_heartbeat_when_backlog_below_threshold():
    inp = TriggerInputs(
        domain="hiring",
        unconsumed_backlog=5,
        last_pass_at=datetime.now(timezone.utc) - timedelta(seconds=200),
        backlog_threshold=30,
        heartbeat_seconds=120,
        now=datetime.now(timezone.utc),
    )
    fired, reason = should_trigger(inp)
    assert fired is True
    assert "heartbeat" in reason


def test_does_not_fire_when_neither_signal_met():
    inp = TriggerInputs(
        domain="hiring",
        unconsumed_backlog=5,
        last_pass_at=datetime.now(timezone.utc) - timedelta(seconds=30),
        backlog_threshold=30,
        heartbeat_seconds=120,
        now=datetime.now(timezone.utc),
    )
    fired, reason = should_trigger(inp)
    assert fired is False
    assert reason  # always provide a human-readable reason


def test_fires_on_heartbeat_when_no_previous_pass_recorded():
    """First-ever pass: last_pass_at=None should be treated as 'long ago'
    so heartbeat fires immediately."""
    inp = TriggerInputs(
        domain="hiring",
        unconsumed_backlog=0,
        last_pass_at=None,
        backlog_threshold=30,
        heartbeat_seconds=120,
        now=datetime.now(timezone.utc),
    )
    fired, reason = should_trigger(inp)
    assert fired is True
    assert "heartbeat" in reason
