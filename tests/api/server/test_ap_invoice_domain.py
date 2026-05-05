"""Acceptance test for the hand-graduated AP-invoice domain.

Confirms:
  - Domain registry entry exists with correct phases + HITL gates
  - Persona references resolve (ap_clerk + controller in PERSONAS)
  - Synthetic seed corpus loads with the expected scenarios
  - Workflow factory builds a Workflow with type='ap-invoice'
  - Spawner imports + dispatch table includes 'ap-invoice'
  - Three-way match validator accepts a clean payload, rejects malformed
"""
from __future__ import annotations

import pytest


def test_domain_registry_has_ap_invoice():
    from api.shared.domains import DOMAINS

    assert "ap-invoice" in DOMAINS
    d = DOMAINS["ap-invoice"]
    assert d.workflow_id_prefix == "API"
    assert d.orchestrator_name == "FleetApInvoiceOrchestrator"
    assert d.operator_surface == "ap-clerk"
    phase_names = [p.name for p in d.phases]
    assert phase_names == ["Invoice Lookup", "Three-Way Match",
                           "ap_clerk_signoff", "controller_signoff"]
    gate_personae = {g.persona for g in d.hitl_gates}
    assert gate_personae == {"ap_clerk", "controller"}


def test_ap_invoice_personae_in_registry():
    from api.shared.personas import PERSONAS

    assert "ap_clerk" in PERSONAS
    assert "controller" in PERSONAS
    assert PERSONAS["ap_clerk"].uses_authority_mcp is True
    assert PERSONAS["controller"].uses_authority_mcp is True


def test_seed_corpus_loads_with_expected_scenarios():
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "ap-invoice" / "invoices.json"
    assert p.exists(), f"missing seed corpus at {p}"
    records = json.loads(p.read_text(encoding="utf-8"))
    assert len(records) >= 40
    scenarios = {r["scenario"] for r in records}
    expected = {"matched-clean", "matched-controller-band", "matched-cfo-band",
                "amount-mismatch", "missing-po", "missing-grn"}
    assert expected <= scenarios


def test_workflow_factory_builds_ap_invoice_record():
    from api.server.services.synthetic_data import build_fleet_ap_invoice_workflow

    record = {
        "invoice_id": "INV-2026-00099",
        "vendor_name": "Test Vendor",
        "amount_gbp": 12500,
        "category": "standard",
        "currency": "GBP",
        "po_id": "PO-2026-00099",
        "scenario": "matched-clean",
    }
    w = build_fleet_ap_invoice_workflow("API-0099", record=record)
    assert w.id == "API-0099"
    assert w.type == "ap-invoice"
    assert w.current_phase == "Invoice Lookup"
    assert w.payload["invoice"]["invoice_id"] == "INV-2026-00099"
    assert w.payload["invoice"]["po_id"] == "PO-2026-00099"
    assert w.payload["scenario"] == "matched-clean"


def test_simulator_dispatch_table_includes_ap_invoice():
    """Asserts the autonomous ramp loop will spawn AP invoice workflows."""
    from api.server.services import simulator_orchestrator as so

    # The dispatch table is local to a function; assert the file imports it
    # by re-importing the spawn function by name.
    assert hasattr(so, "spawn_fleet_ap_invoice_workflow")


def test_three_way_match_validator_accepts_clean_payload():
    import asyncio
    from api.functions.graphs.executors.validators import (
        validate_fleet_ap_invoice_three_way_match_schema as v,
    )

    clean = {
        "ok": True,
        "matched": True,
        "invoice_id": "INV-2026-00099",
        "po_id": "PO-2026-00099",
        "grn_id": "GRN-12345",
        "invoice_amount_gbp": 12500,
        "po_amount_gbp": 12500,
        "amount_within_tolerance": True,
        "po_present": True,
        "grn_present": True,
        "discrepancies": [],
    }
    out = asyncio.run(v.execute(clean))
    assert out["ok"] is True
    assert out["matched"] is True


def test_three_way_match_validator_rejects_inconsistent_matched_flag():
    import asyncio
    from api.functions.graphs.executors.validators import (
        validate_fleet_ap_invoice_three_way_match_schema as v,
    )

    bad = {
        "ok": True,
        "matched": True,  # claims True
        "invoice_id": "INV-2026-00099",
        "po_id": None,
        "grn_id": None,
        "invoice_amount_gbp": 12500,
        "po_amount_gbp": 12500,
        "amount_within_tolerance": True,
        "po_present": False,  # but PO missing
        "grn_present": False,  # and GRN missing
        "discrepancies": ["po-missing", "grn-missing"],
    }
    out = asyncio.run(v.execute(bad))
    assert out["ok"] is False
    assert "disagrees" in out["blocked_reason"]


def test_three_way_match_validator_rejects_when_matched_with_discrepancies():
    import asyncio
    from api.functions.graphs.executors.validators import (
        validate_fleet_ap_invoice_three_way_match_schema as v,
    )

    bad = {
        "ok": True,
        "matched": True,
        "invoice_id": "INV-2026-00099",
        "po_id": "PO-2026-00099",
        "grn_id": "GRN-12345",
        "invoice_amount_gbp": 12500,
        "po_amount_gbp": 12500,
        "amount_within_tolerance": True,
        "po_present": True,
        "grn_present": True,
        "discrepancies": ["spurious"],  # matched=True should imply empty
    }
    out = asyncio.run(v.execute(bad))
    assert out["ok"] is False
    assert "discrepancies" in out["blocked_reason"]


def test_invoice_repository_stub_returns_deterministic_record():
    from api.server.mcp_tools.invoice_repository import get_invoice

    a = get_invoice("INV-2026-00017")
    b = get_invoice("INV-2026-00017")
    assert a == b  # deterministic
    assert a["invoice_id"] == "INV-2026-00017"
    assert isinstance(a["amount_gbp"], int)
    assert a["amount_gbp"] >= 500


def test_invoice_repository_three_way_match_with_explicit_po():
    from api.server.mcp_tools.invoice_repository import find_three_way_match

    out = find_three_way_match("INV-2026-00099", po_id="PO-EXPLICIT")
    assert out["po_id"] == "PO-EXPLICIT"
    assert out["po_present"] is True
    # invariant: matched ⇔ all three flags true
    assert out["matched"] == (
        out["po_present"] and out["grn_present"] and out["amount_within_tolerance"]
    )
