"""Projection: AP invoice (TASK-015).

Maps an ``ap-invoice`` workflow's payload to:

* :class:`Organisation` ``vendor`` — payee.
* :class:`Asset` ``purchase-order`` — matched-to-PO.
* :class:`Money` ``invoice`` — amount + currency.
* :class:`DecisionWrite` for the ``ap_clerk_signoff`` and
  ``controller_signoff`` HITL gates when the workflow payload carries
  matching decision entries (else skipped).

Rels emitted: none. The semantic Money↔Org (payee) and Money↔Asset
(matched-PO) links are typed in the schema as Person→Money / Person→Asset
respectively, so they cannot be expressed today; the cross-cutting context
is preserved via the workflow's ``source_workflows`` array on every
entity, and via ``vendor_id`` / ``po_id`` stashed in Money's ``attributes``
JSON blob. Phase 2's compose-domain v4 will widen the schema if richer
rel directions are needed for FM queries.

Payload keys consumed (verbatim from ``data/synthetic/ap-invoice/invoices.json``)::

    invoice_id, vendor_name, po_id, amount_gbp, currency, category, scenario
"""
from __future__ import annotations

import json

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "ap-invoice"

# Phase 4 Task 4.1: clerk delegation cap. AP invoices above this amount
# escalate to the controller — the clerk-level signoff records 'escalate'
# rather than 'approve'.
DELEGATION_CAP_GBP = 5000.0


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    inv = p.get("invoice") or {}
    invoice_id = str(inv.get("invoice_id") or p.get("invoice_id") or workflow.id)
    vendor_name = str(inv.get("vendor_name") or p.get("vendor_name") or "unknown")
    po_id = str(inv.get("po_id") or p.get("po_id") or "unknown")
    amount = inv.get("amount_gbp") if "amount_gbp" in inv else p.get("amount_gbp")
    amount = amount or 0
    currency = str(inv.get("currency") or p.get("currency") or "GBP")
    category = str(inv.get("category") or p.get("category") or "")

    vendor_id = f"ORG-vendor-{slug(vendor_name)}"
    asset_id = f"ASSET-po-{po_id}"
    money_id = f"MONEY-INV-{invoice_id}"
    sw = (workflow.id,)

    money_extra = {
        "category": category,
        "vendor_id": vendor_id,
        "po_id": asset_id,
        "invoice_id": invoice_id,
    }

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Organisation",
            id=vendor_id,
            attrs={"name": vendor_name, "kind": "vendor"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Asset",
            id=asset_id,
            attrs={"kind": "purchase-order", "identifier": po_id},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Money",
            id=money_id,
            attrs={
                "kind": "invoice",
                "amount": float(amount),
                "currency": currency,
                "attributes": json.dumps(money_extra, sort_keys=True, default=str),
            },
            source_workflows=sw,
        ),
        # NOTE: Money->TRANSACTS->Organisation and Money->OWNS->Asset were
        # removed in Phase 1 hardening. TRANSACTS is schema-typed Person→Money
        # and OWNS is Person→Asset, so writing those edges would raise at
        # link-time. The vendor + PO linkage lives in Money's ``attributes``
        # blob instead until Phase 2 widens the schema.
    ]

    for gate_phase, persona in (
        ("ap_clerk_signoff", "ap_clerk"),
        ("controller_signoff", "controller"),
    ):
        verdict_override = (
            "escalate"
            if gate_phase == "ap_clerk_signoff" and float(amount) > DELEGATION_CAP_GBP
            else None
        )
        d = build_decision(
            workflow,
            gate_phase=gate_phase,
            persona_role=persona,
            source_event="workflow.hitl.requested",
            decided_on=(money_id,),
            attributes={"invoice_id": invoice_id, "amount_gbp": amount},
            verdict_override=verdict_override,
        )
        if d is not None:
            ops.append(d)

    return ops
