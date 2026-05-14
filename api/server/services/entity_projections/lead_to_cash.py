"""Projection: lead-to-cash (pitch-c1).

Emits an Organisation (the client) + a Money node (the booked deal) and
a DecisionWrite at the revenue_recognition HITL gate.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "lead-to-cash"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    d_ = p.get("deal") or {}
    client_name = str(d_.get("client_name") or p.get("client_name") or "unknown")
    deal_value = float(d_.get("deal_value_gbp") or p.get("deal_value_gbp") or 0)

    client_id = f"ORG-client-{slug(client_name)}"
    money_id = f"MONEY-DEAL-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Organisation",
            id=client_id,
            attrs={"name": client_name, "kind": "client"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Money",
            id=money_id,
            attrs={"kind": "deal-revenue", "amount": deal_value, "currency": "GBP"},
            source_workflows=sw,
        ),
    ]

    decision = build_decision(
        workflow,
        gate_phase="revenue_recognition",
        persona_role="account_director",
        source_event="workflow.hitl.requested",
        decided_on=(client_id, money_id),
        attributes={"client_name": client_name, "deal_value_gbp": deal_value},
    )
    if decision is not None:
        ops.append(decision)

    return ops
