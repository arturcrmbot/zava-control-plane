"""Ground-truth providers used by rubric checks.

A ground truth provider knows the 'correct' answer for a seeded synthetic
input. For hiring, that's `data/synthetic/hiring/labels.csv`. Other
domains will get their own implementations.

Plan deviation: rather than backfill an `expected_decision` column into
the shared synthetic data file, `HiringLabelsGroundTruth` derives the
expected decision from `rtw_evidence` when the column is absent, and
prefers the column when it is present. Keeps the synthetic data shape
stable across worktrees.
"""
from __future__ import annotations

import csv
from functools import cached_property
from pathlib import Path
from typing import Protocol

_REJECTION_RTW = frozenset({"", "none", "n/a", "expired"})


class UnknownCandidate(KeyError):
    pass


class HiringGroundTruth(Protocol):
    def expected_decision(self, candidate_id: str) -> str: ...


class HiringLabelsGroundTruth:
    """Reads labels.csv lazily and caches the mapping after first access."""

    def __init__(self, labels_csv: Path) -> None:
        self._labels_csv = labels_csv

    @cached_property
    def _by_candidate(self) -> dict[str, str]:
        result: dict[str, str] = {}
        with self._labels_csv.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                candidate_id = row.get("candidate_id")
                if not candidate_id:
                    continue
                expected = row.get("expected_decision")
                if not expected:
                    expected = self._derive(row)
                result[candidate_id] = expected
        return result

    def expected_decision(self, candidate_id: str) -> str:
        try:
            return self._by_candidate[candidate_id]
        except KeyError as e:
            raise UnknownCandidate(candidate_id) from e

    @staticmethod
    def _derive(row: dict[str, str]) -> str:
        rtw = (row.get("rtw_evidence") or "").strip().lower()
        return "reject" if rtw in _REJECTION_RTW else "approve"
