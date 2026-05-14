"""Tick + burst-on-boot tests for cadenced rituals — pitch-e5."""
from __future__ import annotations

import datetime as _dt

import pytest

from api.server.data_fabric.cadenced_rituals import CADENCED_RITUALS
from api.server.services import cadence_loader


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    cadence_loader.reset_cadenced_rituals_state()
    monkeypatch.delenv("SIMULATOR_CADENCE_BURST", raising=False)
    yield
    cadence_loader.reset_cadenced_rituals_state()


def _recorder():
    spawned: list[str] = []

    def spawn(workflow_type: str) -> None:
        spawned.append(workflow_type)

    return spawned, spawn


def test_burst_via_env_fires_every_ritual_once(monkeypatch):
    monkeypatch.setenv("SIMULATOR_CADENCE_BURST", "1")
    spawned, spawn = _recorder()
    # A "quiet" wall-clock — Tuesday 03:17, no cron matches.
    now = _dt.datetime(2026, 5, 5, 3, 17, 0)

    fired = cadence_loader.tick_cadenced_rituals(spawn_fn=spawn, now=now)

    expected = sorted(r.workflow_type for r in CADENCED_RITUALS)
    assert sorted(spawned) == expected
    assert sorted(fired) == sorted(r.name for r in CADENCED_RITUALS)


def test_burst_only_fires_each_ritual_once_across_ticks(monkeypatch):
    monkeypatch.setenv("SIMULATOR_CADENCE_BURST", "1")
    spawned, spawn = _recorder()
    now = _dt.datetime(2026, 5, 5, 3, 17, 0)
    cadence_loader.tick_cadenced_rituals(spawn_fn=spawn, now=now)
    # Second tick a minute later, still off-cadence — no extra fires.
    later = now + _dt.timedelta(minutes=1)
    extra = cadence_loader.tick_cadenced_rituals(spawn_fn=spawn, now=later)
    assert extra == []
    assert len(spawned) == len(CADENCED_RITUALS)


def test_no_env_only_fires_due_rituals():
    spawned, spawn = _recorder()
    # Monday 2026-05-04 09:00 — only weekly-pitch-review (cron "0 9 * * 1")
    # matches; not the 1st, not Friday, not a quarter month.
    now = _dt.datetime(2026, 5, 4, 9, 0, 0)

    fired = cadence_loader.tick_cadenced_rituals(spawn_fn=spawn, now=now)

    assert fired == ["weekly-pitch-review"]
    assert spawned == ["weekly-pitch-review"]


def test_no_env_quiet_time_fires_nothing():
    spawned, spawn = _recorder()
    # Tuesday 03:17 — no cron matches.
    now = _dt.datetime(2026, 5, 5, 3, 17, 0)

    fired = cadence_loader.tick_cadenced_rituals(spawn_fn=spawn, now=now)

    assert fired == []
    assert spawned == []


def test_due_ritual_fires_only_once_within_same_minute():
    spawned, spawn = _recorder()
    now = _dt.datetime(2026, 5, 4, 9, 0, 0)
    cadence_loader.tick_cadenced_rituals(spawn_fn=spawn, now=now)
    # Same minute, second tick: already fired, last_fire == now, not due.
    again = cadence_loader.tick_cadenced_rituals(spawn_fn=spawn, now=now)
    assert again == []
    assert spawned == ["weekly-pitch-review"]


def test_burst_helper_reads_env(monkeypatch):
    monkeypatch.setenv("SIMULATOR_CADENCE_BURST", "1")
    assert cadence_loader.burst_cadenced_rituals_enabled() is True
    monkeypatch.setenv("SIMULATOR_CADENCE_BURST", "0")
    assert cadence_loader.burst_cadenced_rituals_enabled() is False
    monkeypatch.delenv("SIMULATOR_CADENCE_BURST", raising=False)
    assert cadence_loader.burst_cadenced_rituals_enabled() is False
