"""Test the annual-budget-setting projection (pitch-c3)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.annual_budget_setting import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_annual_budget_setting_emits_period_money_belongs_to():
    payload = {"fiscal_year": "FY2027", "total_gbp": 1000000.0}
    wf = make_workflow("ABS-T1", WORKFLOW_TYPE, payload, nest_under="budget")
    ops = project(wf)
    kinds = {e.kind for e in ops if isinstance(e, EntityWrite)}
    assert {"Period", "Money"} <= kinds
    rels = [o for o in ops if isinstance(o, RelWrite)]
    assert any(r.rel == "BELONGS_TO" for r in rels)
