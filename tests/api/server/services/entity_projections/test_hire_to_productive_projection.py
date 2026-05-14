"""Test the hire-to-productive projection (pitch-c1)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.hire_to_productive import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_hire_to_productive_projection_emits_person_and_period():
    payload = {"joiner_id": "EMP-9001", "role_family": "engineering"}
    wf = make_workflow("H2P-T1", WORKFLOW_TYPE, payload, nest_under="joiner")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    kinds = {e.kind for e in entities}
    assert {"Person", "Period"} <= kinds
    person = next(e for e in entities if e.kind == "Person")
    assert person.id == "PERSON-EMP-9001"
