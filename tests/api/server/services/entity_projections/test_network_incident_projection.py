"""Test the network-incident projection (telco actor-world domain)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.network_incident import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def _incident_payload() -> dict:
    return {
        "incident_site": {
            "id": "SITE-03",
            "region": "north",
            "status": "failed",
            "capacity_mbps": 600.0,
        }
    }


def test_projection_emits_workflow_and_incident_site_asset():
    wf = make_workflow("NI-T1", WORKFLOW_TYPE, _incident_payload(), nest_under="incident")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    kinds = {e.kind for e in entities}
    assert kinds == {"Workflow", "Asset"}

    workflow_node = next(e for e in entities if e.kind == "Workflow")
    assert workflow_node.id == "NI-T1"
    assert workflow_node.attrs["workflow_type"] == "network-incident"

    asset = next(e for e in entities if e.kind == "Asset")
    assert asset.id == "ASSET-site-site-03"
    assert asset.attrs["kind"] == "cell-site"
    assert asset.attrs["identifier"] == "SITE-03"


def test_projection_falls_back_to_workflow_id_without_incident_site():
    wf = make_workflow("NI-T3", WORKFLOW_TYPE, {}, nest_under="incident")
    ops = project(wf)
    asset = next(o for o in ops if isinstance(o, EntityWrite) and o.kind == "Asset")
    assert asset.attrs["identifier"] == "NI-T3"
