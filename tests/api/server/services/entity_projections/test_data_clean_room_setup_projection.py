"""Test the data-clean-room-setup projection (pitch-c3)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.data_clean_room_setup import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def test_data_clean_room_setup_emits_org_and_asset():
    payload = {"partner_org": "DataCo", "data_classes": ["audience"]}
    wf = make_workflow("DCR-T1", WORKFLOW_TYPE, payload, nest_under="clean_room")
    ops = project(wf)
    kinds = {e.kind for e in ops if isinstance(e, EntityWrite)}
    assert {"Organisation", "Asset"} <= kinds
