"""Projection: contract-review (TASK-022).

Payload keys (``data/synthetic/contract-review/contracts.json``)::

    contract_id, vendor_name, contract_type, amount_gbp,
    deviates_from_template, scenario
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

WORKFLOW_TYPE = "contract-review"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    contract_id = str(p.get("contract_id") or workflow.id)
    vendor_name = str(p.get("vendor_name") or "unknown")
    contract_type = str(p.get("contract_type") or "")
    amount = p.get("amount_gbp") or 0
    deviates = bool(p.get("deviates_from_template", False))

    vendor_id = f"ORG-vendor-{slug(vendor_name)}"
    asset_id = f"ASSET-contract-{contract_id}"
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
            attrs={
                "kind": "contract",
                "identifier": contract_id,
                "contract_type": contract_type,
                "deviates_from_template": deviates,
                "amount_gbp": float(amount),
            },
            source_workflows=sw,
        ),
        RelWrite(src_id=asset_id, rel="TRANSACTS", dst_id=vendor_id),
    ]

    d = build_decision(
        workflow,
        gate_phase="approver_signoff",
        persona_role="contracts_counsel",
        source_event="workflow.hitl.requested",
        decided_on=(asset_id,),
        attributes={
            "contract_id": contract_id,
            "contract_type": contract_type,
            "deviates_from_template": deviates,
        },
    )
    if d is not None:
        ops.append(d)

    return ops
