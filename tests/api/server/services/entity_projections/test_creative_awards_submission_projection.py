"""Test the creative-awards-submission projection (pitch-c3)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.creative_awards_submission import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_creative_awards_submission_emits_pitch():
    payload = {"award": "Cannes", "campaign": "Spring2026"}
    wf = make_workflow("CAS-T1", WORKFLOW_TYPE, payload, nest_under="submission")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    assert any(e.kind == "Pitch" for e in entities)
