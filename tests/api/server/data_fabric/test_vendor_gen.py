"""Tests for ``api.server.data_fabric.vendor_gen``.

Per plan/feature-enterprise-pitch-readiness-1.md task pitch-b3.
"""
from __future__ import annotations

from collections import Counter

import pytest

from api.server.data_fabric.vendor_gen import GeneratedVendor, generate_vendors


def test_default_count_is_50():
    vendors = generate_vendors()
    assert len(vendors) == 50
    assert all(isinstance(v, GeneratedVendor) for v in vendors)


def test_ids_unique_and_well_formed():
    vendors = generate_vendors()
    ids = [v.id for v in vendors]
    assert len(set(ids)) == len(ids)
    assert all(v.id.startswith("ORG-vendor-") for v in vendors)
    assert all(v.kind == "vendor" for v in vendors)


@pytest.mark.parametrize("subkind,target", [
    ("production", 15),
    ("freelancer", 10),
    ("software", 7),
    ("ad-tech", 7),
    ("research", 5),
    ("talent-agency", 5),
])
def test_subkind_distribution_within_tolerance(subkind, target):
    counts = Counter(v.subkind for v in generate_vendors())
    assert abs(counts[subkind] - target) <= 2, (
        f"subkind={subkind}: got {counts[subkind]} expected ~{target}"
    )


def test_at_least_one_blocked_vendor():
    vendors = generate_vendors()
    blocked = [v for v in vendors if v.is_blocked]
    assert len(blocked) >= 1
    # Blocked vendors must be red-band (recent KYC failure).
    assert all(v.risk_band == "red" for v in blocked)


def test_determinism_same_seed():
    a = generate_vendors(seed=42)
    b = generate_vendors(seed=42)
    assert a == b


def test_determinism_different_seed_changes_output():
    a = generate_vendors(seed=42)
    b = generate_vendors(seed=43)
    assert a != b


def test_field_value_domains():
    vendors = generate_vendors()
    valid_subkinds = {"production", "freelancer", "software",
                      "ad-tech", "research", "talent-agency"}
    valid_risk = {"green", "amber", "red"}
    valid_terms = {14, 30, 45, 60, 90}
    valid_esg = {"A", "B", "C", "D"}
    for v in vendors:
        assert v.subkind in valid_subkinds
        assert v.risk_band in valid_risk
        assert v.payment_terms_days in valid_terms
        assert v.esg_rating in valid_esg
        if v.subkind == "freelancer":
            assert v.name.endswith("(Freelance)")


def test_count_zero_returns_empty():
    assert generate_vendors(count=0) == []
