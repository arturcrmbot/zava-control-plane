from __future__ import annotations

import pytest

from api.server.services.scoring.types import (
    CheckResult,
    Rubric,
    RubricCheck,
    RunScore,
)


def test_rubric_check_requires_name_and_kind() -> None:
    check = RubricCheck(name="decision_matches_label", kind="decision_matches_label", weight=1.0)
    assert check.name == "decision_matches_label"
    assert check.kind == "decision_matches_label"
    assert check.weight == 1.0
    assert check.params == {}


def test_rubric_check_rejects_non_positive_weight() -> None:
    with pytest.raises(ValueError):
        RubricCheck(name="x", kind="decision_matches_label", weight=0.0)


def test_rubric_weights_sum_to_one_after_normalisation() -> None:
    rubric = Rubric(
        domain="hiring",
        promotion_threshold=0.05,
        min_samples=20,
        checks=(
            RubricCheck(name="match", kind="decision_matches_label", weight=2.0),
            RubricCheck(name="policy", kind="policy_compliance", weight=1.0),
            RubricCheck(name="rationale", kind="rationale_present", weight=1.0),
        ),
    )
    weights = [c.weight for c in rubric.normalised_checks()]
    assert sum(weights) == pytest.approx(1.0)
    assert weights[0] == pytest.approx(0.5)


def test_check_result_score_clamped() -> None:
    ok = CheckResult(name="x", passed=True, score=0.7, detail="")
    assert ok.score == 0.7
    with pytest.raises(ValueError):
        CheckResult(name="x", passed=True, score=1.5, detail="")
    with pytest.raises(ValueError):
        CheckResult(name="x", passed=True, score=-0.1, detail="")


def test_run_score_rollup_weighted_average() -> None:
    rubric = Rubric(
        domain="hiring",
        promotion_threshold=0.05,
        min_samples=20,
        checks=(
            RubricCheck(name="match", kind="decision_matches_label", weight=2.0),
            RubricCheck(name="policy", kind="policy_compliance", weight=1.0),
        ),
    )
    results = (
        CheckResult(name="match", passed=True, score=1.0, detail=""),
        CheckResult(name="policy", passed=True, score=0.5, detail=""),
    )
    rolled = RunScore(workflow_id="WF-1", rubric_domain="hiring", checks=results).rollup(rubric)
    assert rolled == pytest.approx(0.8333, abs=1e-3)
