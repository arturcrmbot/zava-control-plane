"""Test the monthly-client-pnl projection (pitch-c3)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.monthly_client_pnl import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_monthly_client_pnl_emits_org_period_money():
    payload = {"client_name": "Globex", "month": "2026-04", "revenue_gbp": 120000.0}
    wf = make_workflow("MCP-T1", WORKFLOW_TYPE, payload, nest_under="pnl")
    ops = project(wf)
    kinds = {e.kind for e in ops if isinstance(e, EntityWrite)}
    assert {"Organisation", "Period", "Money"} <= kinds
    rels = [o for o in ops if isinstance(o, RelWrite)]
    assert any(r.rel == "BELONGS_TO" for r in rels)
