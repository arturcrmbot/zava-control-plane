"""TASK-008b — trailing-wildcard kill switch matcher."""
from __future__ import annotations

import os
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import pytest

from api.server.services.governance.kill_switch import (
    KillSwitchStore,
    kill_switch_store,
)


@pytest.fixture(autouse=True)
def _fresh():
    kill_switch_store.clear_for_tests()
    yield
    kill_switch_store.clear_for_tests()


def test_ambient_wildcard_blocks_specific_actor():
    store = KillSwitchStore()
    store.add(actor="ambient.*", tool="*", ttl_seconds=60, reason="halt ambient")
    assert store.is_killed("ambient.budget-variance-watcher", "spawn_workflow") is not None
    assert store.is_killed("ambient.vendor-risk-watcher", "anything") is not None
    # Non-ambient actor should NOT match.
    assert store.is_killed("cadence.morning-sweep", "spawn_workflow") is None


def test_cadence_wildcard_blocks_specific_actor():
    store = KillSwitchStore()
    store.add(actor="cadence.*", tool="*", ttl_seconds=60, reason="halt cadence")
    assert store.is_killed("cadence.morning-sweep", "fire") is not None
    assert store.is_killed("ambient.x", "fire") is None


def test_reflector_wildcard_blocks_specific_actor():
    store = KillSwitchStore()
    store.add(actor="reflector.*", tool="*", ttl_seconds=60, reason="halt reflector")
    assert store.is_killed("reflector.entity_reflector", "write") is not None


def test_literal_actor_kill_still_works():
    store = KillSwitchStore()
    store.add(actor="ambient.budget-watcher", tool="spawn_workflow",
              ttl_seconds=60, reason="precise")
    hit = store.is_killed("ambient.budget-watcher", "spawn_workflow")
    assert hit is not None
    # Different actor must not match.
    assert store.is_killed("ambient.other", "spawn_workflow") is None


def test_literal_actor_beats_wildcard_when_both_present():
    store = KillSwitchStore()
    store.add(actor="ambient.*", tool="*", ttl_seconds=60, reason="broad")
    precise = store.add(actor="ambient.budget-watcher", tool="spawn_workflow",
                        ttl_seconds=60, reason="precise")
    hit = store.is_killed("ambient.budget-watcher", "spawn_workflow")
    assert hit is not None
    assert hit.kill_id == precise.kill_id
