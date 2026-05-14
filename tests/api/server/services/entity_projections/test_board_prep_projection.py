"""Test the board-prep projection (pitch-c1)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.board_prep import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_board_prep_projection_emits_period_and_person():
    payload = {"meeting_date": "2026-Q2", "agenda": "quarterly-review"}
    wf = make_workflow("BRD-T1", WORKFLOW_TYPE, payload, nest_under="board_pack")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    kinds = {e.kind for e in entities}
    assert {"Period", "Person"} <= kinds
    person = next(e for e in entities if e.kind == "Person")
    assert person.id == "PERSON-cfo"
