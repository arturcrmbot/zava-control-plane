"""Test the employee-onboarding projection (TASK-018)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.employee_onboarding import (
    project, WORKFLOW_TYPE,
)

from ._helpers import fixture_payload, make_workflow


def test_employee_onboarding_projection_emits_joiner_buddy_and_laptop():
    payload = fixture_payload("employee-onboarding", "joiners.json")
    wf = make_workflow("ONB-T1", WORKFLOW_TYPE, payload, nest_under='joiner')

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]

    persons = [e for e in entities if e.kind == "Person"]
    assets = [e for e in entities if e.kind == "Asset"]
    assert len(persons) == 2
    assert len(assets) == 1
    assert assets[0].attrs["kind"] == "laptop"

    rel_kinds = {r.rel for r in rels}
    assert {"MANAGES", "OWNS"} <= rel_kinds
