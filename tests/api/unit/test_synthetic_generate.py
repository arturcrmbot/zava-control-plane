"""Determinism and distribution tests for the claim generator.

Each test redirects the generator's output paths into pytest's tmp_path so the
tracked `data/synthetic/claims/` and `data/synthetic/labels.csv` are never
mutated by the suite.
"""
from __future__ import annotations
import csv
import json

import pytest

from data.synthetic import generate
from api.shared.expense_taxonomy import CATEGORIES, MARKETS, VERDICTS


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Redirect the generator's output dir + labels file into tmp_path."""
    claims = tmp_path / "claims"
    claims.mkdir()
    labels = tmp_path / "labels.csv"
    monkeypatch.setattr(generate, "CLAIMS", claims)
    monkeypatch.setattr(generate, "LABELS", labels)
    return {"claims": claims, "labels": labels}


def test_generates_300_claims(sandbox):
    generate.run(seed=20260427, count=300)
    assert len(list(sandbox["claims"].glob("CLM-*.json"))) == 300


def test_distribution_within_5pct_of_target(sandbox):
    generate.run(seed=20260427, count=300)
    rows = list(csv.DictReader(sandbox["labels"].open(encoding="utf-8")))
    assert len(rows) == 300
    counts = {v: 0 for v in VERDICTS}
    for r in rows:
        counts[r["gold_label"]] += 1
    # Target 70/20/10 +- 5pp absolute (>=65% green, 15-25% amber, 5-15% red).
    assert 195 <= counts["green"] <= 225, counts
    assert 45 <= counts["amber"] <= 75, counts
    assert 15 <= counts["red"] <= 45, counts


def test_deterministic_seed(tmp_path, monkeypatch):
    """Two runs with the same seed must produce byte-identical outputs."""
    def _run_into(subdir: str) -> list[str]:
        out = tmp_path / subdir
        out.mkdir()
        labels = tmp_path / f"{subdir}.csv"
        monkeypatch.setattr(generate, "CLAIMS", out)
        monkeypatch.setattr(generate, "LABELS", labels)
        generate.run(seed=20260427, count=300)
        return [p.read_text(encoding="utf-8") for p in sorted(out.glob("CLM-*.json"))]

    assert _run_into("first") == _run_into("second")


def test_claim_schema(sandbox):
    generate.run(seed=20260427, count=300)
    sample = json.loads(next(sandbox["claims"].glob("CLM-*.json")).read_text(encoding="utf-8"))
    required = {"claim_id", "employee_id", "submitted_at", "market", "currency", "category",
                "vendor", "amount", "attendees", "receipt_filename", "ems_source",
                "gold_label", "gold_reasoning", "gold_policy_clause"}
    assert required <= set(sample), sorted(required - set(sample))
    assert sample["gold_label"] in set(VERDICTS)
    assert sample["ems_source"] in {"workday", "concur"}
    assert "§" in sample["gold_policy_clause"]


def test_categories_distributed(sandbox):
    generate.run(seed=20260427, count=300)
    rows = list(csv.DictReader(sandbox["labels"].open(encoding="utf-8")))
    assert set(CATEGORIES) <= {r["category"] for r in rows}


def test_markets_distributed(sandbox):
    generate.run(seed=20260427, count=300)
    rows = list(csv.DictReader(sandbox["labels"].open(encoding="utf-8")))
    assert set(MARKETS) <= {r["market"] for r in rows}
