"""Tests for the centralised decision vocabulary."""
from __future__ import annotations

import pytest

from api.server.services.decision_vocab import (
    VERDICTS,
    canonical_verdict,
    is_valid_verdict,
)


def test_known_verdicts_listed():
    assert "approve" in VERDICTS
    assert "reject" in VERDICTS
    assert "escalate" in VERDICTS
    assert "defer" in VERDICTS
    assert "request_changes" in VERDICTS


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("approve", "approve"),
        ("approved", "approve"),
        ("APPROVED", "approve"),
        (" approve ", "approve"),
        ("reject", "reject"),
        ("rejected", "reject"),
        ("escalate", "escalate"),
        ("escalated", "escalate"),
    ],
)
def test_canonical_verdict_normalises(raw, expected):
    assert canonical_verdict(raw) == expected


def test_canonical_verdict_unknown_passes_through():
    # We don't want unknown verdicts to silently become "approve".
    assert canonical_verdict("partial") == "partial"


def test_is_valid_verdict():
    assert is_valid_verdict("approve")
    assert is_valid_verdict("reject")
    assert not is_valid_verdict("approved")  # callers must canonicalise first
    assert not is_valid_verdict("")

from api.server.services.entity_projections import build_decision
from tests.api.server.services.entity_projections._helpers import make_workflow


def test_build_decision_canonicalises_verdict():
    wf = make_workflow(
        "TST-0001", "ap-invoice", {},
        decisions=[{
            "phase": "ap_clerk_signoff", "verdict": "approved",
            "reason": "ok", "decided_at": "2026-05-12T10:00:00",
        }],
    )
    d = build_decision(
        wf, gate_phase="ap_clerk_signoff", persona_role="ap_clerk",
        source_event="workflow.hitl.requested", decided_on=("MONEY-X",),
    )
    assert d is not None
    assert d.verdict == "approve"  # not "approved"


def test_freeze_unfreeze_cap_are_canonical():
    from api.server.services.decision_vocab import canonical_verdict, is_valid_verdict
    for v in ("freeze", "unfreeze", "cap"):
        assert is_valid_verdict(v), f"{v} should be a valid verdict"
        assert canonical_verdict(v) == v
        assert canonical_verdict(v.upper()) == v
        assert canonical_verdict(f"  {v}  ") == v


def test_policy_verdict_aliases():
    from api.server.services.decision_vocab import canonical_verdict
    assert canonical_verdict("frozen") == "freeze"
    assert canonical_verdict("unfrozen") == "unfreeze"
    assert canonical_verdict("capped") == "cap"
