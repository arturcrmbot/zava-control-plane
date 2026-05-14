"""Tests for the magic-link sqlite-backed token store.

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 1.
"""
from __future__ import annotations

import time

import pytest

from api.server.services.magic_link import (
    MagicLinkAlreadyConsumed,
    MagicLinkExpired,
    MagicLinkStore,
)


def test_issue_returns_url_safe_32_char_token(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(candidate_id="C-1", scope="screen", ttl_seconds=60)
    assert len(token) == 32
    assert token.isascii()


def test_consume_within_ttl_returns_payload(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(candidate_id="C-1", scope="screen", ttl_seconds=60)
    payload = store.consume(token, scope="screen")
    assert payload["candidate_id"] == "C-1"


def test_consume_after_expiry_raises(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(candidate_id="C-1", scope="screen", ttl_seconds=0)
    time.sleep(0.05)
    with pytest.raises(MagicLinkExpired):
        store.consume(token, scope="screen")


def test_consume_twice_for_single_use_scope_raises(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(
        candidate_id="C-1", scope="offer", ttl_seconds=60, single_use=True
    )
    store.consume(token, scope="offer")
    with pytest.raises(MagicLinkAlreadyConsumed):
        store.consume(token, scope="offer")


def test_repeatable_read_scope_can_consume_many_times(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(
        candidate_id="C-1", scope="status", ttl_seconds=60, single_use=False
    )
    store.consume(token, scope="status")
    store.consume(token, scope="status")  # no raise


def test_consume_with_wrong_scope_raises(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(candidate_id="C-1", scope="screen", ttl_seconds=60)
    with pytest.raises(ValueError, match="scope mismatch"):
        store.consume(token, scope="offer")


def test_list_active_for_admin_panel(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    store.issue(candidate_id="C-1", scope="status", ttl_seconds=60)
    store.issue(candidate_id="C-2", scope="screen", ttl_seconds=60)
    rows = store.list_active()
    assert len(rows) == 2
    assert {r["candidate_id"] for r in rows} == {"C-1", "C-2"}
