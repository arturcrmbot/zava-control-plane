"""Test the network-incident projection (telco actor-world domain)."""
from __future__ import annotations

from api.server.services.entity_graph import DecisionWrite, EntityWrite
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


def test_projection_reads_legacy_double_nested_incident_payload():
    wf = make_workflow(
        "NI-T2",
        WORKFLOW_TYPE,
        {"incident": _incident_payload()},
        nest_under="incident",
    )

    asset = next(
        op
        for op in project(wf)
        if isinstance(op, EntityWrite) and op.kind == "Asset"
    )

    assert asset.attrs["identifier"] == "SITE-03"


def test_projection_falls_back_to_workflow_id_without_incident_site():
    wf = make_workflow("NI-T3", WORKFLOW_TYPE, {}, nest_under="incident")
    ops = project(wf)
    asset = next(o for o in ops if isinstance(o, EntityWrite) and o.kind == "Asset")
    assert asset.attrs["identifier"] == "NI-T3"


def test_projection_emits_reroute_planning_decision_when_payload_carries_it():
    wf = make_workflow(
        "NI-T4",
        WORKFLOW_TYPE,
        _incident_payload(),
        nest_under="incident",
        decisions=[{
            "phase": "reroute_planning",
            "verdict": "approve",
            "reason": "planned assignment set is valid",
            "decided_at": "2026-07-14T18:00:00Z",
        }],
    )

    decisions = [op for op in project(wf) if isinstance(op, DecisionWrite)]
    assert len(decisions) == 1
    assert decisions[0].phase == "reroute_planning"
