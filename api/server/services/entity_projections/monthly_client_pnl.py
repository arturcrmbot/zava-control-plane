"""Projection: monthly-client-pnl (pitch-c3).

Emits a Period (the month), an Organisation (the client) + a Money
(monthly revenue) + a DecisionWrite at the controller_signoff gate.
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

WORKFLOW_TYPE = "monthly-client-pnl"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    pnl = p.get("pnl") or {}
    client_name = str(pnl.get("client_name") or p.get("client_name") or "unknown")
    month = str(pnl.get("month") or p.get("month") or "unknown")
    revenue = float(pnl.get("revenue_gbp") or p.get("revenue_gbp") or 0)

    client_id = f"ORG-client-{slug(client_name)}"
    period_id = f"PERIOD-month-{month}"
    money_id = f"MONEY-PNL-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Organisation",
            id=client_id,
            attrs={"name": client_name, "kind": "client"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "month", "label": month},
        ),
        EntityWrite(
            kind="Money",
            id=money_id,
            attrs={"kind": "client-revenue", "amount": revenue, "currency": "GBP"},
            source_workflows=sw,
        ),
        RelWrite(src_id=money_id, rel="BELONGS_TO", dst_id=period_id),
    ]

    d = build_decision(
        workflow,
        gate_phase="controller_signoff",
        persona_role="controller",
        source_event="workflow.hitl.requested",
        decided_on=(client_id, period_id, money_id),
        attributes={"client_name": client_name, "month": month, "revenue_gbp": revenue},
    )
    if d is not None:
        ops.append(d)

    return ops
