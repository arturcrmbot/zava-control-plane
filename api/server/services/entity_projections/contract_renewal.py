"""Projection: contract-renewal (TASK-021).

Rels emitted: ``Money -[:BELONGS_TO]-> Period``. Vendor↔contract linkage
is preserved in the Asset's ``attributes`` JSON blob (Asset->TRANSACTS->Org
is schema-invalid; TRANSACTS is Person→Money).

Payload keys (``data/synthetic/contract-renewal/contracts.json``)::

    contract_id, vendor_name, current_annual_value, proposed_annual_value, scenario
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

WORKFLOW_TYPE = "contract-renewal"


def _annual_period_id(created_at: float | None) -> str:
    if not created_at:
        return "PERIOD-2026-annual"
    dt = datetime.fromtimestamp(created_at, tz=timezone.utc)
    return f"PERIOD-{dt.year}-annual"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    contract_id = str(p.get("contract_id") or workflow.id)
    vendor_name = str(p.get("vendor_name") or "unknown")
    current_value = p.get("current_annual_value") or 0
    proposed_value = p.get("proposed_annual_value") or 0

    vendor_id = f"ORG-vendor-{slug(vendor_name)}"
    asset_id = f"ASSET-contract-{contract_id}"
    money_id = f"MONEY-CONTRACT-{contract_id}"
    period_id = _annual_period_id(workflow.created_at)
    sw = (workflow.id,)

    money_extra = {"prior_value": float(current_value), "vendor_id": vendor_id}

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
                "kind": "contract",
                "identifier": contract_id,
                "status": "renewing",
                "attributes": json.dumps({"vendor_id": vendor_id}, sort_keys=True, default=str),
            },
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Money",
            id=money_id,
            attrs={
                "kind": "budget-line",
                "amount": float(proposed_value),
                "currency": "GBP",
                "period": period_id,
                "attributes": json.dumps(money_extra, sort_keys=True, default=str),
            },
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "annual", "label": period_id.removeprefix("PERIOD-")},
        ),
        # NOTE: Asset->TRANSACTS->Organisation dropped in Phase 1 hardening
        # (TRANSACTS is schema-typed Person→Money). Vendor↔contract linkage
        # lives in Asset's ``attributes`` blob until Phase 2.
        RelWrite(src_id=money_id, rel="BELONGS_TO", dst_id=period_id),
    ]

    d = build_decision(
        workflow,
        gate_phase="finance_signoff",
        persona_role="contract_finance_bp",
        source_event="workflow.hitl.requested",
        decided_on=(asset_id, money_id),
        attributes={
            "contract_id": contract_id,
            "current_annual_value": current_value,
            "proposed_annual_value": proposed_value,
        },
    )
    if d is not None:
        ops.append(d)

    return ops
