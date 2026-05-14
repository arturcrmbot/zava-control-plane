"""Test the intercompany-talent-transfer projection (pitch-c3)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.intercompany_talent_transfer import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_intercompany_talent_transfer_emits_person_and_two_orgs():
    payload = {"employee_id": "EMP-9999", "from_subsidiary": "Zava-UK",
               "to_subsidiary": "Zava-DE"}
    wf = make_workflow("ITT-T1", WORKFLOW_TYPE, payload, nest_under="transfer")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    orgs = [e for e in entities if e.kind == "Organisation"]
    assert len(orgs) == 2
    persons = [e for e in entities if e.kind == "Person"]
    assert persons[0].id == "PERSON-EMP-9999"
