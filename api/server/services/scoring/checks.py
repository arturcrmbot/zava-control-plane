"""Built-in rubric check implementations.

A check is a pure function over a list of DecisionRecord (already loaded
from Kuzu by the scorer) returning a CheckResult. Adding a new check kind
means:
  1. Add the literal to CheckKind in types.py.
  2. Add a function here.
  3. Add a dispatch entry in scorer.py._dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass

from api.server.services.scoring.ground_truth import (
    HiringGroundTruth,
    UnknownCandidate,
)
from api.server.services.scoring.types import CheckResult


@dataclass(frozen=True)
class DecisionRecord:
    """Subset of a Kuzu Decision node + its linked candidate that checks need."""
    decision_id: str
    candidate_id: str
    verdict: str
    reason: str
    phase: str


def check_decision_matches_label(
    decisions: list[DecisionRecord],
    *,
    ground_truth: HiringGroundTruth,
) -> CheckResult:
    if not decisions:
        return CheckResult(
            name="decision_matches_label",
            passed=False,
            score=0.0,
            detail="no decisions recorded for run",
        )
    correct = 0
    unknown = 0
    for d in decisions:
        try:
            if ground_truth.expected_decision(d.candidate_id) == d.verdict:
                correct += 1
        except UnknownCandidate:
            unknown += 1
    total = len(decisions)
    score = correct / total
    return CheckResult(
        name="decision_matches_label",
        passed=score == 1.0,
        score=score,
        detail=f"{correct}/{total} matched ground truth ({unknown} unknown candidates)",
    )


def check_policy_compliance(
    decisions: list[DecisionRecord],
    *,
    forbid_blank_reason: bool,
) -> CheckResult:
    if not decisions:
        return CheckResult(
            name="policy_compliance",
            passed=False,
            score=0.0,
            detail="no decisions recorded for run",
        )
    compliant = 0
    for d in decisions:
        ok = True
        if forbid_blank_reason and not d.reason.strip():
            ok = False
        if ok:
            compliant += 1
    total = len(decisions)
    score = compliant / total
    return CheckResult(
        name="policy_compliance",
        passed=score == 1.0,
        score=score,
        detail=f"{compliant}/{total} decisions compliant",
    )


def check_rationale_present(decisions: list[DecisionRecord]) -> CheckResult:
    if not decisions:
        return CheckResult(
            name="rationale_present",
            passed=False,
            score=0.0,
            detail="no decisions recorded for run",
        )
    with_reason = sum(1 for d in decisions if d.reason.strip())
    total = len(decisions)
    score = with_reason / total
    return CheckResult(
        name="rationale_present",
        passed=score == 1.0,
        score=score,
        detail=f"{with_reason}/{total} decisions had a non-blank rationale",
    )
