"""Test the freelancer-onboarding projection (pitch-c3)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.freelancer_onboarding import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_freelancer_onboarding_emits_person():
    payload = {"freelancer_id": "FRL-0001", "discipline": "creative"}
    wf = make_workflow("FOB-T1", WORKFLOW_TYPE, payload, nest_under="freelancer")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    person = next(e for e in entities if e.kind == "Person")
    assert person.id == "PERSON-freelancer-FRL-0001"
