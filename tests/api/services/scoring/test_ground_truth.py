from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.scoring.ground_truth import (
    HiringLabelsGroundTruth,
    UnknownCandidate,
)


def test_expected_decision_lookup(fake_labels_csv: Path) -> None:
    truth = HiringLabelsGroundTruth(labels_csv=fake_labels_csv)
    assert truth.expected_decision("C-001") == "approve"
    assert truth.expected_decision("C-002") == "reject"


def test_unknown_candidate_raises(fake_labels_csv: Path) -> None:
    truth = HiringLabelsGroundTruth(labels_csv=fake_labels_csv)
    with pytest.raises(UnknownCandidate):
        truth.expected_decision("C-999")


def test_loads_lazily_once(fake_labels_csv: Path) -> None:
    truth = HiringLabelsGroundTruth(labels_csv=fake_labels_csv)
    _ = truth.expected_decision("C-001")
    fake_labels_csv.write_text("candidate_id,expected_decision\nC-001,reject\n")
    assert truth.expected_decision("C-001") == "approve"


def test_derives_from_rtw_when_expected_column_missing(
    labels_csv_without_expected_column: Path,
) -> None:
    truth = HiringLabelsGroundTruth(labels_csv=labels_csv_without_expected_column)
    # Anyone with rtw_evidence != 'none'/'' is approved deterministically.
    assert truth.expected_decision("C-100") == "approve"
    assert truth.expected_decision("C-101") == "reject"
    assert truth.expected_decision("C-102") == "approve"


def test_loads_real_hiring_labels_from_repo() -> None:
    """Sanity: the real labels.csv shape is supported without modification."""
    truth = HiringLabelsGroundTruth(labels_csv=Path("data/synthetic/hiring/labels.csv"))
    # Should resolve any seeded candidate without raising.
    assert truth.expected_decision("C-SE-USA-00") in {"approve", "reject"}
