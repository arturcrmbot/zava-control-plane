"""Registry contents test for the per-domain projection registry (TASK-014b).

Locks the registry contract: PROJECTIONS contains the 12 original fleet
domains plus the two legacy domains (``expense-claim``, ``hiring``)
that were wired into the substrate by pitch-a4 so the cosmic lens can
surface them as entities. Adding a new live domain should add an entry
here.
"""
from __future__ import annotations

from api.server.services.entity_projections import PROJECTIONS

EXPECTED_KEYS = frozenset({
    "account-onboarding",     # pitch-c2
    "agency-network-roll-up",  # pitch-c2
    "annual-budget-setting",   # pitch-c3
    "ap-invoice",
    "board-prep",            # pitch-c1
    "client-renewal",          # pitch-c3
    "contract-renewal",
    "contract-review",
    "creative-awards-submission",  # pitch-c3
    "creative-campaign",
    "crisis-response",        # pitch-c2
    "data-clean-room-setup",   # pitch-c3
    "employee-onboarding",
    "expense-claim",       # legacy, wired by pitch-a4
    "freelancer-onboarding",   # pitch-c3
    "fy-close",              # pitch-c1
    "hire-to-productive",    # pitch-c1
    "hiring",              # legacy, wired by pitch-a4
    "intercompany-recharge",  # pitch-c2
    "intercompany-talent-transfer",  # pitch-c3
    "it-access-request",
    "lead-to-cash",          # pitch-c1
    "m-and-a-integration",    # pitch-c2
    "media-pitch-to-win",     # pitch-c2
    "monthly-client-pnl",      # pitch-c3
    "new-business-pipeline-scrub",  # pitch-c3
    "perf-review",
    "privacy-dpia",
    "purchase-order",
    "quarterly-creative-awards",  # pitch-c3
    "talent-redeployment",    # pitch-c2
    "travel-preapproval",
    "treasury-fx",
    "vendor-kyc",
    "vendor-risk-to-pay",    # pitch-c1
    "weekly-pitch-review",     # pitch-c3
})


def test_projections_registry_contains_all_live_domains():
    assert set(PROJECTIONS.keys()) == EXPECTED_KEYS


def test_projections_registry_includes_legacy_domains():
    """pitch-a4 wired the two legacy POC1/POC2 domains into the substrate
    so they materialise into the entity graph alongside the 12 originals.
    """
    assert "expense-claim" in PROJECTIONS
    assert "hiring" in PROJECTIONS


def test_every_projection_is_callable():
    for key, fn in PROJECTIONS.items():
        assert callable(fn), f"projection for {key!r} is not callable"
