"""Projection: AP invoice (TASK-015).

Maps an ``ap-invoice`` workflow's payload to:

* :class:`Organisation` ``vendor`` — payee.
* :class:`Asset` ``purchase-order`` — matched-to-PO.
* :class:`Money` ``invoice`` — amount + currency.
* :class:`RelWrite` ``Money -[:TRANSACTS {role="payee"}]-> Organisation``,
  ``Money -[:OWNS]-> Asset``.
* :class:`DecisionWrite` for the ``ap_clerk_signoff`` and
  ``controller_signoff`` HITL gates when the workflow payload carries
  matching decision entries (else skipped).

Payload keys consumed (verbatim from ``data/synthetic/ap-invoice/invoices.json``)::

    invoice_id, vendor_name, po_id, amount_gbp, currency, category, scenario
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "ap-invoice"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    invoice_id = str(p.get("invoice_id") or workflow.id)
    vendor_name = str(p.get("vendor_name") or "unknown")
    po_id = str(p.get("po_id") or "unknown")
    amount = p.get("amount_gbp") or 0
    currency = str(p.get("currency") or "GBP")
    category = str(p.get("category") or "")

    vendor_id = f"ORG-vendor-{slug(vendor_name)}"
    asset_id = f"ASSET-po-{po_id}"
    money_id = f"MONEY-INV-{invoice_id}"
    sw = (workflow.id,)

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
                "category": category,
            },
            source_workflows=sw,
        ),
        RelWrite(src_id=money_id, rel="TRANSACTS", dst_id=vendor_id, attrs={"role": "payee"}),
        RelWrite(src_id=money_id, rel="OWNS", dst_id=asset_id),
    ]

    for gate_phase, persona in (
        ("ap_clerk_signoff", "ap_clerk"),
        ("controller_signoff", "controller"),
    ):
        d = build_decision(
            workflow,
            gate_phase=gate_phase,
            persona_role=persona,
            source_event="workflow.hitl.requested",
            decided_on=(money_id,),
            attributes={"invoice_id": invoice_id, "amount_gbp": amount},
        )
        if d is not None:
            ops.append(d)

    return ops
