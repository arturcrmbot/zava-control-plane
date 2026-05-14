"""Projection: annual-budget-setting (pitch-c3).

Emits a Period (the fiscal year) + a Money (the topline budget) + a
DecisionWrite at the cfo_signoff gate.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "annual-budget-setting"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    b = p.get("budget") or {}
    fy = str(b.get("fiscal_year") or p.get("fiscal_year") or "FY-unknown")
    total = float(b.get("total_gbp") or p.get("total_gbp") or 0)

    period_id = f"PERIOD-{fy}"
    money_id = f"MONEY-BUDGET-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "fiscal-year", "label": fy},
        ),
        EntityWrite(
            kind="Money",
            id=money_id,
            attrs={"kind": "annual-budget", "amount": total, "currency": "GBP"},
            source_workflows=sw,
        ),
        RelWrite(src_id=money_id, rel="BELONGS_TO", dst_id=period_id),
    ]

    d = build_decision(
        workflow,
        gate_phase="cfo_signoff",
        persona_role="cfo",
        source_event="workflow.hitl.requested",
        decided_on=(period_id, money_id),
        attributes={"fiscal_year": fy, "total_gbp": total},
    )
    if d is not None:
        ops.append(d)

    return ops
