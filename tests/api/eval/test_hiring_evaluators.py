"""Tests for the three POC2 hiring deterministic evaluators added per
plan/feature-foundry-credibility-friday-1.md TASK-015.
"""
from __future__ import annotations

import json

import pytest

from api.server.eval.custom_evaluators import (
    CVFieldExtractionAccuracy,
    JurisdictionRoutingCorrectness,
    ShortlistDecisionMatch,
    _load_hiring_cv,
    _load_hiring_labels,
)


# ---------- ground-truth fixtures --------------------------------------------


@pytest.fixture(scope="module")
def labels() -> dict:
    return _load_hiring_labels()


@pytest.fixture(scope="module")
def first_cv_id(labels) -> str:
    """A candidate that exists in both labels.csv and the cvs/ dir."""
    for cid in labels.keys():
        if _load_hiring_cv(cid) is not None:
            return cid
    pytest.skip("no hiring CV fixtures available")


# ---------- CVFieldExtractionAccuracy ----------------------------------------


def test_cv_field_accuracy_perfect_match(first_cv_id):
    gold = _load_hiring_cv(first_cv_id)
    # Build a "perfectly extracted" payload by echoing gold fields.
    perfect = {
        "candidate_id": first_cv_id,
        "current_title": {"value": gold.get("current_title")},
        "tenure_years_total": {"value": gold.get("tenure_years_total")},
        "right_to_work": gold.get("right_to_work"),
        "level_target": gold.get("level_target"),
    }
    out = CVFieldExtractionAccuracy()(query="", response=json.dumps(perfect))
    assert out["cv_field_accuracy"] == 1.0
    assert out["cv_field_match_count"] == out["cv_field_total"]
    assert out["cv_field_missing_gold"] is False


def test_cv_field_accuracy_partial_match(first_cv_id):
    gold = _load_hiring_cv(first_cv_id)
    partial = {
        "candidate_id": first_cv_id,
        "current_title": {"value": gold.get("current_title")},
        # Wrong tenure
        "tenure_years_total": {"value": 999.0},
        # Right to work present, evidence wrong
        "right_to_work": {
            "jurisdiction": (gold.get("right_to_work") or {}).get("jurisdiction"),
            "evidence": "wrong_evidence",
        },
        "level_target": gold.get("level_target"),
    }
    out = CVFieldExtractionAccuracy()(query="", response=json.dumps(partial))
    assert 0 < out["cv_field_accuracy"] < 1
    assert out["cv_per_field"]["current_title"]["match"] == 1
    assert out["cv_per_field"]["tenure_years_total"]["match"] == 0
    assert out["cv_per_field"]["right_to_work.jurisdiction"]["match"] == 1
    assert out["cv_per_field"]["right_to_work.evidence"]["match"] == 0


def test_cv_field_accuracy_no_gold_for_unknown_candidate():
    out = CVFieldExtractionAccuracy()(
        query="",
        response=json.dumps({"candidate_id": "C-XXX-NOPE-99",
                              "current_title": {"value": "X"}}),
    )
    assert out["cv_field_accuracy"] == 0.0
    assert out["cv_field_missing_gold"] is True


def test_cv_field_accuracy_handles_unparseable_response():
    out = CVFieldExtractionAccuracy()(query="", response="not json at all")
    assert out["cv_field_accuracy"] == 0.0
    assert out["cv_field_missing_gold"] is True


# ---------- ShortlistDecisionMatch -------------------------------------------


def test_shortlist_match_strong_for_real_candidate(first_cv_id):
    out = ShortlistDecisionMatch()(
        query="",
        response=json.dumps({"candidate_id": first_cv_id, "verdict": "strong"}),
    )
    assert out["shortlist_match"] == 1
    assert out["shortlist_confusion"] == "tp"


def test_shortlist_match_borderline_counts_as_pass(first_cv_id):
    out = ShortlistDecisionMatch()(
        query="",
        response=json.dumps({"candidate_id": first_cv_id, "verdict": "borderline"}),
    )
    assert out["shortlist_match"] == 1
    assert out["shortlist_confusion"] == "tp"


def test_shortlist_low_for_real_candidate_is_false_negative(first_cv_id):
    out = ShortlistDecisionMatch()(
        query="",
        response=json.dumps({"candidate_id": first_cv_id, "verdict": "low"}),
    )
    assert out["shortlist_match"] == 0
    assert out["shortlist_confusion"] == "fn"


def test_shortlist_missing_verdict_returns_missing():
    out = ShortlistDecisionMatch()(
        query="",
        response=json.dumps({"candidate_id": "C-XXX"}),
    )
    assert out["shortlist_match"] == 0
    assert out["shortlist_confusion"] == "missing"


# ---------- JurisdictionRoutingCorrectness ----------------------------------


def test_jurisdiction_match_correct(labels, first_cv_id):
    gold_jur = labels[first_cv_id]["jurisdiction"]
    out = JurisdictionRoutingCorrectness()(
        query="",
        response=json.dumps({"candidate_id": first_cv_id, "jurisdiction": gold_jur}),
    )
    assert out["jurisdiction_match"] == 1
    assert out["jurisdiction_predicted"] == gold_jur.upper()
    assert out["jurisdiction_gold"] == gold_jur.upper()


def test_jurisdiction_match_wrong(first_cv_id):
    out = JurisdictionRoutingCorrectness()(
        query="",
        response=json.dumps({"candidate_id": first_cv_id, "jurisdiction": "BR"}),
    )
    assert out["jurisdiction_match"] == 0


def test_jurisdiction_match_missing_gold():
    out = JurisdictionRoutingCorrectness()(
        query="",
        response=json.dumps({"candidate_id": "C-XXX-NOPE", "jurisdiction": "USA"}),
    )
    assert out["jurisdiction_match"] == 0
    assert out["jurisdiction_missing_gold"] is True


def test_jurisdiction_accepts_alternate_keys(first_cv_id, labels):
    gold_jur = labels[first_cv_id]["jurisdiction"]
    out = JurisdictionRoutingCorrectness()(
        query="",
        response=json.dumps({"candidate_id": first_cv_id, "routed_to": gold_jur}),
    )
    assert out["jurisdiction_match"] == 1
