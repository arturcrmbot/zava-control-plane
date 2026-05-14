"""Acceptance tests for the wave-2 hand-graduated domains:
  - purchase-order
  - contract-review
  - privacy-dpia
  - treasury-fx

Each domain is verified for:
  - Domain registry entry with correct phases + HITL gate
  - Default approver persona is in PERSONAS
  - Synthetic seed corpus loads with expected scenarios
  - Workflow factory builds a Workflow with the right type
  - Spawn function importable
  - Schema validator accepts a clean payload
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


# --------------------------------------------------------------------------
# purchase-order
# --------------------------------------------------------------------------
def test_purchase_order_registry_entry():
    from api.shared.domains import DOMAINS

    d = DOMAINS["purchase-order"]
    assert d.workflow_id_prefix == "POW"
    assert d.orchestrator_name == "FleetPurchaseOrderOrchestrator"
    phase_names = [p.name for p in d.phases]
    assert phase_names == ["PO Lookup", "Supplier Check",
                           "Authority Resolve", "approver_signoff"]
    assert {g.persona for g in d.hitl_gates} == {"line_manager"}
    assert d.hitl_gates[0].external_event == "purchase_order_approval_decision"


def test_purchase_order_corpus_loads():
    p = REPO_ROOT / "data" / "synthetic" / "purchase-order" / "pos.json"
    records = json.loads(p.read_text(encoding="utf-8"))
    assert len(records) >= 40
    scenarios = {r["scenario"] for r in records}
    assert {
        "low-band-line-manager",
        "mid-band-category-manager",
        "high-band-sourcing-lead",
        "top-band-cpo",
        "unapproved-supplier",
    } <= scenarios


def test_purchase_order_workflow_factory():
    from api.server.services.synthetic_data import build_fleet_purchase_order_workflow

    record = {
        "po_id": "PO-2026-00099",
        "vendor_name": "Test",
        "amount_gbp": 4000,
        "category": "standard",
        "supplier_on_approved_list": True,
        "scenario": "low-band-line-manager",
    }
    w = build_fleet_purchase_order_workflow("POW-0099", record=record)
    assert w.id == "POW-0099"
    assert w.type == "purchase-order"
    assert w.current_phase == "PO Lookup"
    assert w.payload["purchase_order"]["po_id"] == "PO-2026-00099"
    assert w.payload["scenario"] == "low-band-line-manager"


def test_purchase_order_spawn_fn_importable():
    from api.server.services.simulator_orchestrator import spawn_fleet_purchase_order_workflow
    assert callable(spawn_fleet_purchase_order_workflow)


def test_purchase_order_supplier_check_validator_clean():
    from api.functions.graphs.executors.validators import (
        validate_fleet_purchase_order_supplier_check_schema as v,
    )
    out = asyncio.run(v.execute({
        "ok": True,
        "po_id": "PO-X",
        "supplier_on_approved_list": True,
        "amount_gbp": 1000,
        "category": "standard",
        "flags": [],
    }))
    assert out["ok"] is True


# --------------------------------------------------------------------------
# contract-review
# --------------------------------------------------------------------------
def test_contract_review_registry_entry():
    from api.shared.domains import DOMAINS

    d = DOMAINS["contract-review"]
    assert d.workflow_id_prefix == "CRW"
    assert d.orchestrator_name == "FleetContractReviewOrchestrator"
    phase_names = [p.name for p in d.phases]
    assert phase_names == ["Contract Intake", "Risk Classify",
                           "Authority Resolve", "approver_signoff"]
    assert {g.persona for g in d.hitl_gates} == {"contracts_counsel"}
    assert d.hitl_gates[0].external_event == "contract_review_signoff_decision"


def test_contract_review_corpus_loads():
    p = REPO_ROOT / "data" / "synthetic" / "contract-review" / "contracts.json"
    records = json.loads(p.read_text(encoding="utf-8"))
    assert len(records) >= 40
    scenarios = {r["scenario"] for r in records}
    assert {
        "nda-template",
        "nda-deviation",
        "msa-standard",
        "msa-material",
        "msa-deviation",
    } <= scenarios


def test_contract_review_workflow_factory():
    from api.server.services.synthetic_data import build_fleet_contract_review_workflow

    record = {
        "contract_id": "CR-2026-00099",
        "vendor_name": "Test",
        "contract_type": "msa",
        "amount_gbp": 75000,
        "deviates_from_template": False,
        "scenario": "msa-standard",
    }
    w = build_fleet_contract_review_workflow("CRW-0099", record=record)
    assert w.type == "contract-review"
    assert w.current_phase == "Contract Intake"
    assert w.payload["contract_review"]["contract_id"] == "CR-2026-00099"


def test_contract_review_risk_classify_validator_clean():
    from api.functions.graphs.executors.validators import (
        validate_fleet_contract_review_risk_classify_schema as v,
    )
    out = asyncio.run(v.execute({
        "ok": True,
        "contract_type": "msa",
        "amount_gbp": 50000,
        "deviates_from_template": False,
        "category": "msa",
        "flags": [],
    }))
    assert out["ok"] is True


def test_contract_review_risk_classify_validator_rejects_unknown_type():
    from api.functions.graphs.executors.validators import (
        validate_fleet_contract_review_risk_classify_schema as v,
    )
    out = asyncio.run(v.execute({
        "ok": True,
        "contract_type": "invalid-type",
        "amount_gbp": 1000,
        "deviates_from_template": False,
        "category": "x",
        "flags": [],
    }))
    assert out["ok"] is False


# --------------------------------------------------------------------------
# privacy-dpia
# --------------------------------------------------------------------------
def test_privacy_dpia_registry_entry():
    from api.shared.domains import DOMAINS

    d = DOMAINS["privacy-dpia"]
    assert d.workflow_id_prefix == "DPI"
    assert d.orchestrator_name == "FleetPrivacyDpiaOrchestrator"
    phase_names = [p.name for p in d.phases]
    assert phase_names == ["DPIA Intake", "Risk Classify",
                           "Authority Resolve", "approver_signoff"]
    assert {g.persona for g in d.hitl_gates} == {"dpo"}
    assert d.hitl_gates[0].external_event == "dpia_signoff_decision"


def test_privacy_dpia_corpus_loads():
    p = REPO_ROOT / "data" / "synthetic" / "privacy-dpia" / "dpias.json"
    records = json.loads(p.read_text(encoding="utf-8"))
    assert len(records) >= 30
    scenarios = {r["scenario"] for r in records}
    assert any(s.startswith("low-risk") for s in scenarios)
    assert any(s.startswith("high-risk") for s in scenarios)


def test_privacy_dpia_workflow_factory():
    from api.server.services.synthetic_data import build_fleet_privacy_dpia_workflow

    record = {
        "dpia_id": "DPIA-2026-00099",
        "system_name": "Test System",
        "risk_tier": "high_risk",
        "geography": "EMEA",
        "scenario": "high-risk-emea",
    }
    w = build_fleet_privacy_dpia_workflow("DPI-0099", record=record)
    assert w.type == "privacy-dpia"
    assert w.current_phase == "DPIA Intake"
    assert w.payload["dpia"]["risk_tier"] == "high_risk"


def test_privacy_dpia_risk_classify_validator_clean():
    from api.functions.graphs.executors.validators import (
        validate_fleet_privacy_dpia_risk_classify_schema as v,
    )
    out = asyncio.run(v.execute({
        "ok": True,
        "risk_tier": "low_risk",
        "geography": "AMER",
        "category": "low_risk",
        "flags": [],
    }))
    assert out["ok"] is True


# --------------------------------------------------------------------------
# treasury-fx
# --------------------------------------------------------------------------
def test_treasury_fx_registry_entry():
    from api.shared.domains import DOMAINS

    d = DOMAINS["treasury-fx"]
    assert d.workflow_id_prefix == "TFX"
    assert d.orchestrator_name == "FleetTreasuryFxOrchestrator"
    phase_names = [p.name for p in d.phases]
    assert phase_names == ["Op Lookup", "Position Check",
                           "Authority Resolve", "approver_signoff"]
    assert {g.persona for g in d.hitl_gates} == {"treasurer"}
    assert d.hitl_gates[0].external_event == "treasury_signoff_decision"


def test_treasury_fx_corpus_loads():
    p = REPO_ROOT / "data" / "synthetic" / "treasury-fx" / "ops.json"
    records = json.loads(p.read_text(encoding="utf-8"))
    assert len(records) >= 30
    scenarios = {r["scenario"] for r in records}
    assert "treasurer-band" in scenarios
    assert "cfo-band" in scenarios


def test_treasury_fx_workflow_factory():
    from api.server.services.synthetic_data import build_fleet_treasury_fx_workflow

    record = {
        "op_id": "FX-2026-00099",
        "op_kind": "spot-hedge",
        "currency_pair": "GBP/USD",
        "notional_gbp": 500000,
        "scenario": "treasurer-band",
    }
    w = build_fleet_treasury_fx_workflow("TFX-0099", record=record)
    assert w.type == "treasury-fx"
    assert w.current_phase == "Op Lookup"
    assert w.payload["treasury_op"]["notional_gbp"] == 500000


def test_treasury_fx_position_check_validator_clean():
    from api.functions.graphs.executors.validators import (
        validate_fleet_treasury_fx_position_check_schema as v,
    )
    out = asyncio.run(v.execute({
        "ok": True,
        "currency_pair": "GBP/USD",
        "notional_gbp": 250000,
        "pair_limit_gbp": 5_000_000,
        "within_limit": True,
        "category": "standard",
        "flags": [],
    }))
    assert out["ok"] is True


def test_treasury_fx_position_check_validator_rejects_lying_within_limit():
    from api.functions.graphs.executors.validators import (
        validate_fleet_treasury_fx_position_check_schema as v,
    )
    out = asyncio.run(v.execute({
        "ok": True,
        "currency_pair": "GBP/USD",
        "notional_gbp": 10_000_000,
        "pair_limit_gbp": 5_000_000,
        "within_limit": True,  # lies
        "category": "standard",
        "flags": [],
    }))
    assert out["ok"] is False


# --------------------------------------------------------------------------
# Personae existence
# --------------------------------------------------------------------------
def test_new_personae_registered():
    from api.shared.personas import PERSONAS
    for p in ("cfo", "finance_controller", "category_manager", "sourcing_lead",
              "cpo", "contracts_counsel", "gc", "dpo", "treasurer", "line_manager"):
        assert p in PERSONAS, f"persona {p!r} not in PERSONAS"


def test_new_personae_skill_files_exist():
    base = REPO_ROOT / "api" / "server" / "personae"
    for p in ("cfo", "finance_controller"):
        assert (base / p / "SKILL.md").exists(), f"{p}/SKILL.md missing"
