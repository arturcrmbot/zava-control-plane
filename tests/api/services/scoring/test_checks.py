from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.server.services.scoring.checks import (
    DecisionRecord,
    check_decision_matches_label,
    check_policy_compliance,
    check_rationale_present,
)


def _decision(
    verdict: str = "approve",
    reason: str = "level match",
    candidate_id: str = "C-001",
) -> DecisionRecord:
    return DecisionRecord(
        decision_id="d-1",
        candidate_id=candidate_id,
        verdict=verdict,
        reason=reason,
        phase="arbitrate",
    )


def test_decision_matches_label_passes_when_correct() -> None:
    truth = MagicMock()
    truth.expected_decision.return_value = "approve"
    result = check_decision_matches_label([_decision("approve")], ground_truth=truth)
    assert result.passed is True
    assert result.score == pytest.approx(1.0)


def test_decision_matches_label_partial_credit() -> None:
    truth = MagicMock()
    truth.expected_decision.side_effect = ["approve", "approve", "approve", "approve"]
    decisions = [_decision("approve", candidate_id=f"C-00{i}") for i in range(1, 5)]
    decisions[3] = _decision("reject", candidate_id="C-004")
    result = check_decision_matches_label(decisions, ground_truth=truth)
    assert result.score == pytest.approx(0.75)
    assert result.passed is False


def test_decision_matches_label_handles_empty_run() -> None:
    truth = MagicMock()
    result = check_decision_matches_label([], ground_truth=truth)
    assert result.score == 0.0
    assert "no decisions" in result.detail.lower()


def test_policy_compliance_forbid_blank_reason() -> None:
    decisions = [_decision(reason=""), _decision(reason="ok")]
    result = check_policy_compliance(decisions, forbid_blank_reason=True)
    assert result.score == pytest.approx(0.5)
    assert result.passed is False


def test_rationale_present_full_when_all_have_reasons() -> None:
    decisions = [_decision(reason="a"), _decision(reason="b")]
    result = check_rationale_present(decisions)
    assert result.score == pytest.approx(1.0)
    assert result.passed is True


def test_rationale_present_zero_when_all_blank() -> None:
    decisions = [_decision(reason=""), _decision(reason="   ")]
    result = check_rationale_present(decisions)
    assert result.score == pytest.approx(0.0)
