"""Test the network-incident projection (telco actor-world domain)."""
from __future__ import annotations

import json

import pytest

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from verticals.telco.entity_projections.network_incident import (
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


def test_projection_connects_affected_service_to_incident_site():
    incident = _incident_payload()
    incident["affected_sessions"] = [
        {"id": "SESS-00001", "subscriber_id": "SUB-00001", "kind": "voice"}
    ]
    wf = make_workflow("NI-T5", WORKFLOW_TYPE, incident, nest_under="incident")

    ops = project(wf)

    services = [
        op
        for op in ops
        if isinstance(op, EntityWrite) and op.attrs.get("kind") == "network-session"
    ]
    assert [service.id for service in services] == ["ASSET-session-sess-00001"]
    assert RelWrite(
        src_id="ASSET-session-sess-00001",
        rel="HOSTED_ON",
        dst_id="ASSET-site-site-03",
    ) in ops


def test_projection_caps_sessions_to_deterministic_prefix_and_keeps_exact_count(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TELCO_GRAPH_DETAIL_CAP", "2")
    incident = _incident_payload()
    incident["affected_sessions"] = [
        {
            "id": f"SESS-{index:05d}",
            "subscriber_id": f"SUB-{index:05d}",
            "kind": "voice",
        }
        for index in range(1, 5)
    ]
    wf = make_workflow("NI-CAP", WORKFLOW_TYPE, incident, nest_under="incident")

    first = project(wf)
    second = project(wf)

    services = [
        op
        for op in first
        if isinstance(op, EntityWrite) and op.attrs.get("kind") == "network-session"
    ]
    assert [service.id for service in services] == [
        "ASSET-session-sess-00001",
        "ASSET-session-sess-00002",
    ]
    assert first == second

    site = next(
        op
        for op in first
        if isinstance(op, EntityWrite) and op.attrs.get("kind") == "cell-site"
    )
    assert json.loads(site.attrs["attributes"])["affected_session_count"] == 4


def test_projection_defaults_to_25_session_details(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("TELCO_GRAPH_DETAIL_CAP", raising=False)
    incident = _incident_payload()
    incident["affected_sessions"] = [
        {"id": f"SESS-{index:05d}", "subscriber_id": f"SUB-{index:05d}"}
        for index in range(30)
    ]
    wf = make_workflow("NI-DEFAULT-CAP", WORKFLOW_TYPE, incident, nest_under="incident")

    services = [
        op
        for op in project(wf)
        if isinstance(op, EntityWrite) and op.attrs.get("kind") == "network-session"
    ]

    assert len(services) == 25
    assert services[-1].id == "ASSET-session-sess-00024"


@pytest.mark.parametrize("value", ["", "0", "-1", "not-an-integer"])
def test_projection_rejects_invalid_graph_detail_cap(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
):
    monkeypatch.setenv("TELCO_GRAPH_DETAIL_CAP", value)
    wf = make_workflow("NI-BAD-CAP", WORKFLOW_TYPE, _incident_payload(), nest_under="incident")

    with pytest.raises(ValueError, match="TELCO_GRAPH_DETAIL_CAP.*positive integer"):
        project(wf)
