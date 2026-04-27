"""Determinism and distribution tests for the claim generator."""
from __future__ import annotations
import csv
import json
import shutil
from pathlib import Path

import pytest

from data.synthetic import generate

DATA = Path(generate.__file__).parent
CLAIMS = DATA / "claims"
LABELS = DATA / "labels.csv"


@pytest.fixture(autouse=True)
def _clean_outputs():
    if CLAIMS.exists():
        for p in CLAIMS.glob("CLM-*.json"):
            p.unlink()
    if LABELS.exists():
        LABELS.unlink()
    yield


def test_generates_300_claims():
    generate.run(seed=20260427, count=300)
    claim_files = sorted(CLAIMS.glob("CLM-*.json"))
    assert len(claim_files) == 300


def test_distribution_within_5pct_of_target():
    generate.run(seed=20260427, count=300)
    rows = list(csv.DictReader(LABELS.open(encoding="utf-8")))
    assert len(rows) == 300
    counts = {"green": 0, "amber": 0, "red": 0}
    for r in rows:
        counts[r["gold_label"]] += 1
    # Target 70/20/10 +- 5pp absolute (i.e. >=65% green, 15-25% amber, 5-15% red).
    assert 195 <= counts["green"] <= 225, counts
    assert 45 <= counts["amber"] <= 75, counts
    assert 15 <= counts["red"] <= 45, counts


def test_deterministic_seed():
    generate.run(seed=20260427, count=300)
    first = sorted(CLAIMS.glob("CLM-*.json"))
    first_payloads = [p.read_text(encoding="utf-8") for p in first]
    for p in CLAIMS.glob("CLM-*.json"):
        p.unlink()
    LABELS.unlink()
    generate.run(seed=20260427, count=300)
    second = sorted(CLAIMS.glob("CLM-*.json"))
    second_payloads = [p.read_text(encoding="utf-8") for p in second]
    assert first_payloads == second_payloads


def test_claim_schema():
    generate.run(seed=20260427, count=300)
    sample = json.loads(next(CLAIMS.glob("CLM-*.json")).read_text(encoding="utf-8"))
    required = {"claim_id", "employee_id", "submitted_at", "market", "currency", "category",
                "vendor", "amount", "attendees", "receipt_filename", "ems_source",
                "gold_label", "gold_reasoning", "gold_policy_clause"}
    assert required <= set(sample), sorted(required - set(sample))
    assert sample["gold_label"] in {"green", "amber", "red"}
    assert sample["ems_source"] in {"workday", "concur"}
    assert "§" in sample["gold_policy_clause"]


def test_categories_distributed():
    generate.run(seed=20260427, count=300)
    rows = list(csv.DictReader(LABELS.open(encoding="utf-8")))
    cats = {r["category"] for r in rows}
    assert {"meals", "travel", "accommodation", "entertainment", "miscellaneous"} <= cats


def test_markets_distributed():
    generate.run(seed=20260427, count=300)
    rows = list(csv.DictReader(LABELS.open(encoding="utf-8")))
    markets = {r["market"] for r in rows}
    assert {"UK", "US", "DE", "IN"} <= markets
