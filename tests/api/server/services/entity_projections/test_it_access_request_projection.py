"""Test the it-access-request projection (TASK-019)."""
from __future__ import annotations

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from api.server.services.entity_projections import it_access_request
from api.server.services.entity_projections.it_access_request import (
    _line_manager_oo,
    project,
    WORKFLOW_TYPE,
)

from ._helpers import fixture_payload, make_workflow


def test_it_access_request_projection_emits_person_and_access_grant():
    payload = fixture_payload("it-access-request", "requests.json")
    wf = make_workflow("ITAR-T1", WORKFLOW_TYPE, payload, nest_under='request')

    ops = project(wf)
    entities = {e.kind: e for e in ops if isinstance(e, EntityWrite)}
    rels = [o for o in ops if isinstance(o, RelWrite)]

    assert "Person" in entities and "Asset" in entities
    assert entities["Asset"].attrs["kind"] == "access-grant"
    assert entities["Asset"].id == f"ASSET-access-{wf.id}"

    assert any(r.rel == "OWNS" for r in rels)


def test_it_access_defers_when_manager_oo():
    wf_id = "IT-DEFER-4"
    assert _line_manager_oo(wf_id), "test fixture id needs to deterministically hash to OOO"
    wf = make_workflow(
        wf_id,
        "it-access-request",
        {
            "employee_id": "EMP-1",
            "department": "Engineering",
            "requested_role_templates": ["github"],
            "business_justification": "demo",
            "scenario": "demo",
        },
        nest_under="request",
        decisions=[
            {"phase": "line_manager_approval", "verdict": "approved", "reason": "ok",
             "decided_at": "2026-05-12T10:00:00"},
            {"phase": "it_admin_approval", "verdict": "approved", "reason": "ok",
             "decided_at": "2026-05-12T11:00:00"},
        ],
    )
    ops = it_access_request.project(wf)
    decisions = {d.phase: d for d in ops if isinstance(d, DecisionWrite)}
    assert decisions["line_manager_approval"].verdict == "defer"
    assert decisions["it_admin_approval"].verdict == "approve"


def test_it_access_approves_when_manager_present():
    wf_id = "IT-DEFER-1"
    assert not _line_manager_oo(wf_id), "fixture id must NOT hash to OOO"
    wf = make_workflow(
        wf_id,
        "it-access-request",
        {
            "employee_id": "EMP-2",
            "department": "Engineering",
            "requested_role_templates": ["github"],
            "business_justification": "demo",
            "scenario": "demo",
        },
        nest_under="request",
        decisions=[
            {"phase": "line_manager_approval", "verdict": "approved", "reason": "ok",
             "decided_at": "2026-05-12T10:00:00"},
        ],
    )
    ops = it_access_request.project(wf)
    decisions = {d.phase: d for d in ops if isinstance(d, DecisionWrite)}
    assert decisions["line_manager_approval"].verdict == "approve"
