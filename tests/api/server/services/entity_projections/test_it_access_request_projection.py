"""Test the it-access-request projection (TASK-019)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.it_access_request import (
    project, WORKFLOW_TYPE,
)

from ._helpers import fixture_payload, make_workflow


def test_it_access_request_projection_emits_person_and_access_grant():
    payload = fixture_payload("it-access-request", "requests.json")
    wf = make_workflow("ITAR-T1", WORKFLOW_TYPE, payload)

    ops = project(wf)
    entities = {e.kind: e for e in ops if isinstance(e, EntityWrite)}
    rels = [o for o in ops if isinstance(o, RelWrite)]

    assert "Person" in entities and "Asset" in entities
    assert entities["Asset"].attrs["kind"] == "access-grant"
    assert entities["Asset"].id == f"ASSET-access-{wf.id}"

    assert any(r.rel == "OWNS" for r in rels)
