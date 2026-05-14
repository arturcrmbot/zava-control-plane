"""Test the fy-close projection (pitch-c1)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.fy_close import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_fy_close_projection_emits_period_and_org():
    payload = {"fiscal_year": "FY2026", "entity": "Zava-Group"}
    wf = make_workflow("FYC-T1", WORKFLOW_TYPE, payload, nest_under="close")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    kinds = {e.kind for e in entities}
    assert {"Period", "Organisation"} <= kinds
    period = next(e for e in entities if e.kind == "Period")
    assert period.id == "PERIOD-FY2026"
