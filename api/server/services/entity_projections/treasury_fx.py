"""Projection: treasury-fx (TASK-025).

Rels emitted: none.

Payload keys (``data/synthetic/treasury-fx/ops.json``)::

    op_id, op_kind, currency_pair, notional_gbp, scenario
"""
from __future__ import annotations

import json

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "treasury-fx"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    op = p.get("treasury_op") or {}
    op_id = str(op.get("op_id") or p.get("op_id") or workflow.id)
    op_kind = str(op.get("op_kind") or p.get("op_kind") or "")
    pair = str(op.get("currency_pair") or p.get("currency_pair") or "")
    notional = (op.get("notional_gbp") if "notional_gbp" in op else p.get("notional_gbp")) or 0

    money_id = f"MONEY-FX-{op_id}"
    sw = (workflow.id,)

    money_extra = {"op_kind": op_kind, "currency_pair": pair}

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Money",
            id=money_id,
            attrs={
                "kind": "fx",
                "amount": float(notional),
                "currency": "GBP",
                "attributes": json.dumps(money_extra, sort_keys=True, default=str),
            },
            source_workflows=sw,
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="approver_signoff",
        persona_role="treasurer",
        source_event="workflow.hitl.requested",
        decided_on=(money_id,),
        attributes={"op_id": op_id, "op_kind": op_kind, "currency_pair": pair, "notional_gbp": notional},
    )
    if d is not None:
        ops.append(d)

    return ops
