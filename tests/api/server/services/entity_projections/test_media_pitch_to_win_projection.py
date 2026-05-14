"""Test the media-pitch-to-win meta-workflow projection (pitch-c2)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.media_pitch_to_win import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_media_pitch_to_win_projection_emits_workflow_node():
    wf = make_workflow("MPW-T1", WORKFLOW_TYPE, {"meta_kind": WORKFLOW_TYPE}, nest_under="meta")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    assert len(entities) == 1
    assert entities[0].kind == "Workflow"
    assert entities[0].id == "MPW-T1"
    assert entities[0].attrs["workflow_type"] == "media-pitch-to-win"
