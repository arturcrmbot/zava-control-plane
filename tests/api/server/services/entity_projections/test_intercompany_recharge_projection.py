"""Test the intercompany-recharge meta-workflow projection (pitch-c2)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.intercompany_recharge import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_intercompany_recharge_projection_emits_workflow_node():
    wf = make_workflow("ICR-T1", WORKFLOW_TYPE, {"meta_kind": WORKFLOW_TYPE}, nest_under="meta")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    assert len(entities) == 1
    assert entities[0].kind == "Workflow"
    assert entities[0].id == "ICR-T1"
    assert entities[0].attrs["workflow_type"] == "intercompany-recharge"
