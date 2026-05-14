"""Projection: vendor-risk-to-pay (pitch-c1).

Emits an Organisation (the vendor) + a Money node (the pending payment)
+ a DecisionWrite at the payment_release HITL gate.
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

WORKFLOW_TYPE = "vendor-risk-to-pay"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    v = p.get("vendor_payment") or {}
    vendor_name = str(v.get("vendor_name") or p.get("vendor_name") or "unknown")
    amount = float(v.get("amount_gbp") or p.get("amount_gbp") or 0)

    vendor_id = f"ORG-vendor-{slug(vendor_name)}"
    money_id = f"MONEY-VRP-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Organisation",
            id=vendor_id,
            attrs={"name": vendor_name, "kind": "vendor"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Money",
            id=money_id,
            attrs={
                "kind": "vendor-payment",
                "amount": amount,
                "currency": "GBP",
            },
            source_workflows=sw,
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="payment_release",
        persona_role="vendor_kyc_finance_bp",
        source_event="workflow.hitl.requested",
        decided_on=(vendor_id, money_id),
        attributes={"vendor_name": vendor_name, "amount_gbp": amount},
    )
    if d is not None:
        ops.append(d)

    return ops
