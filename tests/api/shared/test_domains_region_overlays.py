"""Pitch-c4: per-region overlays on Domain.

Validates that:
- ``RegionOverlay`` is exposed and shaped as documented.
- A handful of (domain, region) pairs declare the expected overlays.
- ``Domain.phases_for_region`` returns base phases for unknown regions
  and base + overlay extras for declared regions.
"""
from __future__ import annotations

from api.shared.domains import (
    DOMAINS,
    Domain,
    HitlGate,
    Phase,
    RegionOverlay,
)


def test_region_overlay_dataclass_shape():
    overlay = RegionOverlay(
        extra_phases=(Phase("X", "deterministic"),),
        policy_threshold_overrides={"k": 1.0},
        extra_hitl_gates=(),
    )
    assert overlay.extra_phases[0].name == "X"
    assert overlay.policy_threshold_overrides == {"k": 1.0}
    assert overlay.extra_hitl_gates == ()


def test_region_overlay_defaults_empty():
    overlay = RegionOverlay()
    assert overlay.extra_phases == ()
    assert overlay.policy_threshold_overrides == {}
    assert overlay.extra_hitl_gates == ()


def test_domain_default_region_overlays_empty():
    # Most domains carry no overlays — default factory must yield {}.
    no_overlay_domains = [
        d for d in DOMAINS.values() if not d.region_overlays
    ]
    assert len(no_overlay_domains) >= 1


def test_expense_claim_de_overlay_present():
    d = DOMAINS["expense-claim"]
    assert "DE" in d.region_overlays
    de = d.region_overlays["DE"]
    names = [p.name for p in de.extra_phases]
    assert "Works-Council Notify" in names
    assert "auto_approve_max_eur" in de.policy_threshold_overrides


def test_expense_claim_us_overlay_present():
    d = DOMAINS["expense-claim"]
    assert "US" in d.region_overlays
    us = d.region_overlays["US"]
    assert any("Monthly" in p.name for p in us.extra_phases)


def test_vendor_kyc_de_overlay_present():
    d = DOMAINS["vendor-kyc"]
    assert "DE" in d.region_overlays
    de = d.region_overlays["DE"]
    assert any("BaFin" in p.name for p in de.extra_phases)


def test_contract_renewal_jp_overlay_present():
    d = DOMAINS["contract-renewal"]
    assert "JP" in d.region_overlays
    jp = d.region_overlays["JP"]
    assert any("Stamp-Tax" in p.name for p in jp.extra_phases)


def test_phases_for_region_unknown_returns_base():
    d = DOMAINS["expense-claim"]
    base = d.phases
    assert d.phases_for_region("ZZ") == base
    assert d.phases_for_region(None) == base
    assert d.phases_for_region("") == base


def test_phases_for_region_de_appends_extras():
    d = DOMAINS["expense-claim"]
    base = d.phases
    de_phases = d.phases_for_region("DE")
    assert len(de_phases) == len(base) + 1
    assert de_phases[: len(base)] == base
    assert de_phases[-1].name == "Works-Council Notify"


def test_phases_for_region_jp_contract_renewal():
    d = DOMAINS["contract-renewal"]
    jp_phases = d.phases_for_region("JP")
    assert len(jp_phases) >= 6  # 5 base + 1 extra
    assert jp_phases[-1].name == "Stamp-Tax Validate"


def test_phases_for_region_overlay_does_not_mutate_base():
    d = DOMAINS["expense-claim"]
    before = d.phases
    _ = d.phases_for_region("DE")
    after = d.phases
    assert before == after


def test_domain_dataclass_has_region_overlays_field():
    # Schema check — every Domain instance carries the field.
    for d in DOMAINS.values():
        assert isinstance(d, Domain)
        assert isinstance(d.region_overlays, dict)


def test_overlay_extra_hitl_gates_typing():
    # Overlays may declare extra HITL gates; the field accepts an empty
    # tuple by default and HitlGate instances when populated.
    overlay = RegionOverlay(
        extra_hitl_gates=(
            HitlGate("works_council", "works_council_decision", "line_manager"),
        ),
    )
    assert overlay.extra_hitl_gates[0].persona == "line_manager"
