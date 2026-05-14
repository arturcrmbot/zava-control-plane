"""Pitch I4 — routing optimiser unit tests.

Stats record/aggregate correctly; ``preferred_role`` ignores
under-sampled candidates; ties break by experience (I6 hook) then by
position in the candidate list.
"""
from __future__ import annotations

import pytest

from api.server.services import persona_experience, routing_stats


@pytest.fixture(autouse=True)
def _clean():
    routing_stats.reset()
    persona_experience.reset()
    yield
    routing_stats.reset()
    persona_experience.reset()


def test_record_aggregates_per_role():
    for _ in range(7):
        routing_stats.record("ap_invoice", "controller_review", "controller",
                             approved=True)
    routing_stats.record("ap_invoice", "controller_review", "controller",
                         approved=False)

    s = routing_stats.stats_for("ap_invoice", "controller_review", "controller")
    assert s == {"approves": 7, "total": 8}
    assert routing_stats.approval_rate(
        "ap_invoice", "controller_review", "controller"
    ) == pytest.approx(7 / 8)


def test_record_ignores_blank_axes():
    routing_stats.record(None, "g", "r", approved=True)
    routing_stats.record("d", None, "r", approved=True)
    routing_stats.record("d", "g", None, approved=True)
    assert routing_stats.snapshot() == {}


def test_preferred_role_returns_none_when_under_sampled():
    # Only 4 samples — below MIN_SAMPLES.
    for _ in range(4):
        routing_stats.record("ap_invoice", "review", "delegate", approved=True)
    assert routing_stats.preferred_role(
        "ap_invoice", "review", ["delegate", "boss"]
    ) is None


def test_preferred_role_picks_highest_approval_rate():
    for _ in range(10):
        routing_stats.record("ap_invoice", "review", "delegate", approved=True)
    for _ in range(10):
        routing_stats.record("ap_invoice", "review", "boss", approved=False)
    assert routing_stats.preferred_role(
        "ap_invoice", "review", ["boss", "delegate"]
    ) == "delegate"


def test_preferred_role_tie_breaks_on_experience():
    # Both 100% approval at 10 samples — experience picks the winner.
    for role in ("alice", "bob"):
        for _ in range(10):
            routing_stats.record("ap_invoice", "review", role, approved=True)
    persona_experience.record_decision("alice", "ap_invoice")
    persona_experience.record_decision("alice", "ap_invoice")
    persona_experience.record_decision("bob", "ap_invoice")

    pick = routing_stats.preferred_role(
        "ap_invoice", "review", ["bob", "alice"],
    )
    assert pick == "alice", "more-experienced (alice=2 > bob=1) must win the tie"


def test_preferred_role_tie_falls_back_to_first_listed_when_experience_equal():
    for role in ("delegate", "boss"):
        for _ in range(10):
            routing_stats.record("ap_invoice", "review", role, approved=True)
    # Equal experience (both 0). Caller passes the more-junior delegate
    # first → optimiser routes work down by default.
    assert routing_stats.preferred_role(
        "ap_invoice", "review", ["delegate", "boss"],
    ) == "delegate"


def test_preferred_role_skips_under_sampled_candidate():
    """A well-sampled candidate beats an under-sampled one even with low rate."""
    # boss: 10 samples, 50% approval
    for i in range(10):
        routing_stats.record("ap_invoice", "review", "boss",
                             approved=(i < 5))
    # delegate: 3 samples, 100% approval — but ineligible (< 5).
    for _ in range(3):
        routing_stats.record("ap_invoice", "review", "delegate", approved=True)

    assert routing_stats.preferred_role(
        "ap_invoice", "review", ["delegate", "boss"],
    ) == "boss"


def test_snapshot_serialises_keys():
    routing_stats.record("d", "g", "r", approved=True)
    routing_stats.record("d", "g", "r", approved=False)
    snap = routing_stats.snapshot()
    assert "d|g|r" in snap
    row = snap["d|g|r"]
    assert row["approves"] == 1
    assert row["total"] == 2
    assert row["approval_rate"] == 0.5
    assert row["domain"] == "d"
    assert row["gate"] == "g"
    assert row["role"] == "r"


def test_preferred_role_empty_candidates_is_none():
    assert routing_stats.preferred_role("d", "g", []) is None


def test_preferred_role_missing_axes_is_none():
    routing_stats.record("d", "g", "r", approved=True)
    assert routing_stats.preferred_role(None, "g", ["r"]) is None
    assert routing_stats.preferred_role("d", None, ["r"]) is None
