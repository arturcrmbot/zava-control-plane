"""Seed-corpus structural validation — every per-domain JSON has the
required fields, scenario tags within the documented allow-list, and a
minimum size.

Per TASK-034 of plan/feature-fleet-domain-substrate-1.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


SPECS = {
    "data/synthetic/travel-preapproval/trips.json": {
        "required": ("id", "employee_id", "origin", "destination",
                     "depart_date", "return_date", "business_reason", "scenario"),
        "scenarios": {"in-policy", "policy-exception", "high-cost-band"},
    },
    "data/synthetic/vendor-kyc/vendors.json": {
        "required": ("id", "vendor_name", "country_of_incorporation",
                     "proposing_agency", "scenario"),
        "scenarios": {"clean", "sanctions-hit-entity",
                      "sanctions-hit-ubo", "adverse-media"},
    },
    "data/synthetic/employee-onboarding/joiners.json": {
        "required": ("id", "employee_id", "department", "buddy_id",
                     "start_date", "scenario"),
        "scenarios": {"standard", "elevated-access-request",
                      "external-contractor"},
    },
    "data/synthetic/it-access-request/requests.json": {
        "required": ("id", "employee_id", "department",
                     "requested_role_templates", "business_justification",
                     "scenario"),
        "scenarios": {"routine-rotation", "privileged-broad",
                      "post-incident-narrow"},
    },
    "data/synthetic/contract-renewal/contracts.json": {
        "required": ("id", "contract_id", "vendor_name",
                     "current_annual_value", "proposed_annual_value", "scenario"),
        "scenarios": {"flat-renewal", "price-jump", "scope-expansion",
                      "below-market"},
    },
    "data/synthetic/perf-review/reviewees.json": {
        "required": ("id", "employee_id", "cycle", "prior_rating", "scenario"),
        "scenarios": {"on-track", "calibration-outlier-high",
                      "calibration-outlier-low", "promotion-candidate"},
    },
}


@pytest.mark.parametrize("rel,spec", SPECS.items())
def test_corpus_structure(rel, spec):
    path = REPO_ROOT / rel
    assert path.exists(), f"missing seed corpus {rel}"
    records = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(records, list), f"{rel} must be a list"
    assert len(records) >= 40, f"{rel} has only {len(records)} records (need >=40)"
    seen_ids: set[str] = set()
    for i, r in enumerate(records):
        for field in spec["required"]:
            assert field in r, f"{rel}[{i}] missing required field {field!r}"
        assert r["scenario"] in spec["scenarios"], (
            f"{rel}[{i}] scenario={r['scenario']!r} not in "
            f"{sorted(spec['scenarios'])}"
        )
        assert r["id"] not in seen_ids, f"{rel} has duplicate id {r['id']!r}"
        seen_ids.add(r["id"])
