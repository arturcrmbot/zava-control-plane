"""Test the travel-preapproval projection (TASK-020)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.travel_preapproval import (
    project, WORKFLOW_TYPE,
)

from ._helpers import fixture_payload, make_workflow


def test_travel_preapproval_projection_emits_person_places_and_period():
    payload = fixture_payload("travel-preapproval", "trips.json")
    wf = make_workflow("TRV-T1", WORKFLOW_TYPE, payload)

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]
    kinds = {e.kind for e in entities}

    assert {"Person", "Place", "Period"} <= kinds
    places = [e for e in entities if e.kind == "Place"]
    assert len(places) == 2
    assert all(p.attrs["kind"] == "airport" for p in places)
    assert any(r.rel == "LOCATED_IN" for r in rels)
