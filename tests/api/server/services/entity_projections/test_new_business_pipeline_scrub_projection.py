"""Test the new-business-pipeline-scrub projection (pitch-c3)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.new_business_pipeline_scrub import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_new_business_pipeline_scrub_emits_period_and_pitch():
    payload = {"week_label": "W14", "pipeline_count": 24}
    wf = make_workflow("NBP-T1", WORKFLOW_TYPE, payload, nest_under="scrub")
    ops = project(wf)
    kinds = {e.kind for e in ops if isinstance(e, EntityWrite)}
    assert {"Period", "Pitch"} <= kinds
