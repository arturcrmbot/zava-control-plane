"""Test the AP-invoice projection (TASK-015)."""
from __future__ import annotations

import json

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from api.server.services.entity_projections import ap_invoice
from api.server.services.entity_projections.ap_invoice import project, WORKFLOW_TYPE

from ._helpers import fixture_payload, make_workflow


def test_ap_invoice_projection_emits_core_entities():
    payload = fixture_payload("ap-invoice", "invoices.json")
    wf = make_workflow("API-T1", WORKFLOW_TYPE, payload, nest_under='invoice')

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]
    kinds = {e.kind for e in entities}

    assert "Organisation" in kinds
    assert "Asset" in kinds
    assert "Money" in kinds

    money = next(e for e in entities if e.kind == "Money")
    assert money.id == f"MONEY-INV-{payload['invoice_id']}"
    assert money.attrs["amount"] == float(payload["amount_gbp"])
    assert money.attrs["currency"] == payload["currency"]

    # ``category`` is not a Money schema column — must live in the
    # ``attributes`` JSON blob (Phase 1 hardening).
    extra = json.loads(money.attrs["attributes"])
    assert extra["category"] == payload["category"]
    assert extra["vendor_id"].startswith("ORG-vendor-")
    assert extra["po_id"] == f"ASSET-po-{payload['po_id']}"

    # No rels — Money->TRANSACTS->Org and Money->OWNS->Asset are dropped
    # because the schema types those rels Person→Money / Person→Asset.
    assert rels == []


def test_ap_invoice_escalates_when_over_delegation_cap():
    wf = make_workflow(
        "AP-OVER-1",
        "ap-invoice",
        {
            "invoice_id": "INV-100",
            "amount_gbp": 12000.0,
            "vendor_name": "Globex",
            "po_id": "PO-100",
            "currency": "GBP",
            "category": "services",
        },
        nest_under="invoice",
        decisions=[
            {"phase": "ap_clerk_signoff", "verdict": "approved", "reason": "ok",
             "decided_at": "2026-05-12T10:00:00"},
            {"phase": "controller_signoff", "verdict": "approved", "reason": "ok",
             "decided_at": "2026-05-12T11:00:00"},
        ],
    )
    ops = ap_invoice.project(wf)
    decisions = {d.phase: d for d in ops if isinstance(d, DecisionWrite)}
    assert decisions["ap_clerk_signoff"].verdict == "escalate"
    assert decisions["controller_signoff"].verdict == "approve"


def test_ap_invoice_approves_when_under_delegation_cap():
    wf = make_workflow(
        "AP-UNDER-1",
        "ap-invoice",
        {
            "invoice_id": "INV-101",
            "amount_gbp": 1500.0,
            "vendor_name": "Globex",
            "po_id": "PO-101",
            "currency": "GBP",
            "category": "services",
        },
        nest_under="invoice",
        decisions=[
            {"phase": "ap_clerk_signoff", "verdict": "approved", "reason": "ok",
             "decided_at": "2026-05-12T10:00:00"},
        ],
    )
    ops = ap_invoice.project(wf)
    decisions = {d.phase: d for d in ops if isinstance(d, DecisionWrite)}
    assert decisions["ap_clerk_signoff"].verdict == "approve"
