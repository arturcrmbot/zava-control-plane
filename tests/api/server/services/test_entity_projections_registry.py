"""Registry contents test for the per-domain projection registry (TASK-014b).

Locks the CON-001 contract: PROJECTIONS must contain exactly the 12 fleet
domains and **must not** contain the POC1/POC2 hand-built domains
(``expense-claim``, ``hiring``) — those run through their own bespoke
orchestrators and are intentionally excluded from the substrate's
projection layer.
"""
from __future__ import annotations

from api.server.services.entity_projections import PROJECTIONS

EXPECTED_KEYS = frozenset({
    "ap-invoice",
    "contract-renewal",
    "contract-review",
    "creative-campaign",
    "employee-onboarding",
    "it-access-request",
    "perf-review",
    "privacy-dpia",
    "purchase-order",
    "travel-preapproval",
    "treasury-fx",
    "vendor-kyc",
})


def test_projections_registry_contains_exactly_the_twelve_fleet_domains():
    assert set(PROJECTIONS.keys()) == EXPECTED_KEYS


def test_projections_registry_excludes_poc1_and_poc2_domains():
    assert "expense-claim" not in PROJECTIONS
    assert "hiring" not in PROJECTIONS


def test_every_projection_is_callable():
    for key, fn in PROJECTIONS.items():
        assert callable(fn), f"projection for {key!r} is not callable"
