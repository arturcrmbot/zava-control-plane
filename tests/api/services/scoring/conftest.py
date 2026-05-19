from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fake_labels_csv(tmp_path: Path) -> Path:
    path = tmp_path / "labels.csv"
    path.write_text(
        "candidate_id,role,jurisdiction,rtw_evidence,expected_decision\n"
        "C-001,engineer,UK,passport,approve\n"
        "C-002,engineer,UK,none,reject\n"
        "C-003,manager,US,visa,approve\n"
    )
    return path


@pytest.fixture
def labels_csv_without_expected_column(tmp_path: Path) -> Path:
    """Matches the real data/synthetic/hiring/labels.csv shape (no expected_decision)."""
    path = tmp_path / "labels.csv"
    path.write_text(
        "candidate_id,role,jurisdiction,rtw_evidence\n"
        "C-100,engineer,USA,us_citizen\n"
        "C-101,engineer,UK,none\n"
        "C-102,manager,DE,visa\n"
    )
    return path
