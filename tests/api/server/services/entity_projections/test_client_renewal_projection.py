"""Test the client-renewal projection (pitch-c3 + pitch-h6)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.client_renewal import (
    CHILD_WORKFLOW_TYPES, project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def _ops_for(workflow_id: str = "CLR-T1") -> list:
    payload = {"client_name": "Globex", "annual_value_gbp": 250000.0,
               "brand_name": "GlobexBrand"}
    wf = make_workflow(workflow_id, WORKFLOW_TYPE, payload, nest_under="renewal")
    return project(wf)


def test_client_renewal_emits_pitch_and_campaign():
    ops = _ops_for()
    kinds = {e.kind for e in ops if isinstance(e, EntityWrite)}
    assert {"Organisation", "Pitch", "Campaign", "Workflow"} <= kinds


def test_client_renewal_emits_three_sub_workflow_children():
    """pitch-h6: client-renewal cascades into MSA + DPIA + portfolio review."""
    ops = _ops_for("CLR-T2")
    child_workflows = [
        e for e in ops
        if isinstance(e, EntityWrite) and e.kind == "Workflow"
        and e.id != "CLR-T2"
    ]
    types = sorted(e.attrs["workflow_type"] for e in child_workflows)
    assert types == sorted(CHILD_WORKFLOW_TYPES)


def test_client_renewal_emits_three_sub_workflow_of_rels():
    """pitch-h6: each child has a SUB_WORKFLOW_OF rel from the parent."""
    ops = _ops_for("CLR-T3")
    rels = [r for r in ops if isinstance(r, RelWrite) and r.rel == "SUB_WORKFLOW_OF"]
    assert len(rels) == 3
    assert all(r.src_id == "CLR-T3" for r in rels)
    child_ids = {r.dst_id for r in rels}
    expected = {f"WF-{ct}-CLR-T3" for ct in CHILD_WORKFLOW_TYPES}
    assert child_ids == expected

