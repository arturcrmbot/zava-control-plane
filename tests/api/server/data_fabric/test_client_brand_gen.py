"""Tests for ``api.server.data_fabric.client_brand_gen``.

Per plan/feature-enterprise-pitch-readiness-1.md task pitch-b4.
"""
from __future__ import annotations

from collections import Counter

from api.server.data_fabric.client_brand_gen import (
    GeneratedBrand,
    GeneratedClient,
    generate_clients_and_brands,
)


def test_default_client_count_is_six():
    clients, _ = generate_clients_and_brands()
    assert len(clients) == 6
    assert all(isinstance(c, GeneratedClient) for c in clients)


def test_tier_distribution_exact_2_3_1():
    clients, _ = generate_clients_and_brands()
    counts = Counter(c.tier for c in clients)
    assert counts == {"enterprise": 2, "mid-market": 3, "smb": 1}


def test_brand_count_around_ten():
    _, brands = generate_clients_and_brands()
    assert 8 <= len(brands) <= 11
    assert all(isinstance(b, GeneratedBrand) for b in brands)


def test_each_brand_resolves_to_a_client():
    clients, brands = generate_clients_and_brands()
    client_ids = {c.id for c in clients}
    for b in brands:
        assert b.client_id in client_ids, f"orphan brand {b.id}"


def test_brands_per_client_matches_tier_rules():
    clients, brands = generate_clients_and_brands()
    by_client: dict[str, int] = {}
    for b in brands:
        by_client[b.client_id] = by_client.get(b.client_id, 0) + 1
    for c in clients:
        n = by_client.get(c.id, 0)
        if c.tier == "enterprise":
            assert n == 2
        elif c.tier == "mid-market":
            assert n in (1, 2)
        else:  # smb
            assert n == 1


def test_budget_within_tier_range():
    clients, brands = generate_clients_and_brands()
    tier_by_client = {c.id: c.tier for c in clients}
    bounds = {
        "enterprise": (5_000_000.0, 20_000_000.0),
        "mid-market": (1_000_000.0, 5_000_000.0),
        "smb":        (100_000.0, 500_000.0),
    }
    for b in brands:
        low, high = bounds[tier_by_client[b.client_id]]
        assert low <= b.annual_budget_gbp <= high, (
            f"brand {b.id} budget {b.annual_budget_gbp} out of {low}-{high}"
        )


def test_ids_are_unique_and_well_formed():
    clients, brands = generate_clients_and_brands()
    cids = [c.id for c in clients]
    bids = [b.id for b in brands]
    assert len(set(cids)) == len(cids)
    assert len(set(bids)) == len(bids)
    assert all(c.id.startswith("ORG-client-") for c in clients)
    assert all(b.id.startswith("BRAND-") for b in brands)


def test_field_value_domains():
    clients, brands = generate_clients_and_brands()
    valid_industries = {"fmcg", "pharma", "fintech", "auto", "retail", "tech"}
    valid_segments = {"mass", "premium", "niche"}
    for c in clients:
        assert c.industry in valid_industries
        assert c.tier in {"enterprise", "mid-market", "smb"}
        assert c.annual_revenue_gbp > 0
    for b in brands:
        assert b.market_segment in valid_segments


def test_determinism():
    a = generate_clients_and_brands(seed=42)
    b = generate_clients_and_brands(seed=42)
    assert a == b
    c = generate_clients_and_brands(seed=43)
    assert a != c


def test_zero_count_returns_empty():
    clients, brands = generate_clients_and_brands(client_count=0)
    assert clients == [] and brands == []
