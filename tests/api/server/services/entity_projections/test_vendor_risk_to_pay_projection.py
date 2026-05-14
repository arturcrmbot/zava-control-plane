"""Test the vendor-risk-to-pay projection (pitch-c1)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.vendor_risk_to_pay import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_vendor_risk_to_pay_projection_emits_org_and_money():
    payload = {"vendor_name": "Acme Holdings", "amount_gbp": 25000.0}
    wf = make_workflow("VRP-T1", WORKFLOW_TYPE, payload, nest_under="vendor_payment")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    kinds = {e.kind for e in entities}
    assert {"Organisation", "Money"} <= kinds
    money = next(e for e in entities if e.kind == "Money")
    assert money.attrs["amount"] == 25000.0
    assert money.attrs["kind"] == "vendor-payment"
