"""Test the quarterly-creative-awards projection (pitch-c3)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.quarterly_creative_awards import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_quarterly_creative_awards_emits_period_and_pitch():
    payload = {"quarter": "2026-Q2", "shortlist_size": 12}
    wf = make_workflow("QCA-T1", WORKFLOW_TYPE, payload, nest_under="quarterly_awards")
    ops = project(wf)
    kinds = {e.kind for e in ops if isinstance(e, EntityWrite)}
    assert {"Period", "Pitch"} <= kinds
