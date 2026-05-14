"""Test the lead-to-cash projection (pitch-c1)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.lead_to_cash import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_lead_to_cash_projection_emits_org_and_money():
    payload = {"client_name": "Globex Corp", "deal_value_gbp": 80000.0}
    wf = make_workflow("L2C-T1", WORKFLOW_TYPE, payload, nest_under="deal")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    kinds = {e.kind for e in entities}
    assert {"Organisation", "Money"} <= kinds
    money = next(e for e in entities if e.kind == "Money")
    assert money.attrs["kind"] == "deal-revenue"
    assert money.attrs["amount"] == 80000.0
