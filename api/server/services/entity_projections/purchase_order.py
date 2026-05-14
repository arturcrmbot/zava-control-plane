"""Projection: purchase-order (TASK-016).

Rels emitted: ``Money -[:BELONGS_TO]-> Period``. Asset->TRANSACTS->Org
was dropped in Phase 1 hardening (TRANSACTS is schema-typed Person→Money);
vendor↔PO linkage is preserved in Asset's ``attributes`` blob.

Payload keys (``data/synthetic/purchase-order/pos.json``)::

    po_id, vendor_name, amount_gbp, category, supplier_on_approved_list, scenario

The PO's budget-line :class:`Money` belongs to the current quarter
:class:`Period`. We derive the period from ``workflow.created_at`` (epoch
seconds) and fall back to ``"PERIOD-2026-Q2"`` when unavailable.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "purchase-order"


def _period_id(created_at: float | None) -> str:
    if not created_at:
        return "PERIOD-2026-Q2"
    dt = datetime.fromtimestamp(created_at, tz=timezone.utc)
    quarter = (dt.month - 1) // 3 + 1
    return f"PERIOD-{dt.year}-Q{quarter}"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    po = p.get("purchase_order") or {}
    po_id = str(po.get("po_id") or p.get("po_id") or workflow.id)
    vendor_name = str(po.get("vendor_name") or p.get("vendor_name") or "unknown")
    amount = (po.get("amount_gbp") if "amount_gbp" in po else p.get("amount_gbp")) or 0
    category = str(po.get("category") or p.get("category") or "")
    approved = bool(po.get("supplier_on_approved_list",
                           p.get("supplier_on_approved_list", False)))

    vendor_id = f"ORG-vendor-{slug(vendor_name)}"
    asset_id = f"ASSET-po-{po_id}"
    money_id = f"MONEY-PO-{po_id}"
    period_id = _period_id(workflow.created_at)
    sw = (workflow.id,)

    asset_extra = {
        "category": category,
        "approved_supplier": approved,
        "vendor_id": vendor_id,
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
            attrs={
                "kind": "purchase-order",
                "identifier": po_id,
                "attributes": json.dumps(asset_extra, sort_keys=True, default=str),
            },
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Money",
            id=money_id,
            attrs={
                "kind": "budget-line",
                "amount": float(amount),
                "currency": "GBP",
                "period": period_id,
            },
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "quarter", "label": period_id.removeprefix("PERIOD-")},
        ),
        # NOTE: Asset->TRANSACTS->Organisation dropped in Phase 1 hardening.
        RelWrite(src_id=money_id, rel="BELONGS_TO", dst_id=period_id),
    ]

    # Both gates feed off the single ``approver_signoff`` HITL gate today
    # (compose-domain v3 collapses the line-manager / finance-bp split into
    # an Authority Resolve step). We still emit a DecisionWrite when the
    # payload carries one to keep the schema-evolution path open.
    d = build_decision(
        workflow,
        gate_phase="approver_signoff",
        persona_role="line_manager",
        source_event="workflow.hitl.requested",
        decided_on=(asset_id, money_id),
        attributes={"po_id": po_id, "amount_gbp": amount},
    )
    if d is not None:
        ops.append(d)

    return ops
