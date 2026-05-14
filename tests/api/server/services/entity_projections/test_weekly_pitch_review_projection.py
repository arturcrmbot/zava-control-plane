"""Test the weekly-pitch-review projection (pitch-c3)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.weekly_pitch_review import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_weekly_pitch_review_emits_period_and_pitch():
    payload = {"week_label": "W14", "pitch_count": 7}
    wf = make_workflow("WPR-T1", WORKFLOW_TYPE, payload, nest_under="review")
    ops = project(wf)
    kinds = {e.kind for e in ops if isinstance(e, EntityWrite)}
    assert {"Period", "Pitch"} <= kinds
