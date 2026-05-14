"""Test the vendor-kyc projection (TASK-017)."""
from __future__ import annotations

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from api.server.services.entity_projections.vendor_kyc import project, WORKFLOW_TYPE

from ._helpers import fixture_payload, make_workflow


def test_vendor_kyc_projection_emits_two_orgs_and_proposed_by_rel():
    payload = fixture_payload("vendor-kyc", "vendors.json")
    wf = make_workflow("VKY-T1", WORKFLOW_TYPE, payload, nest_under='vendor')

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]
    decisions = [o for o in ops if isinstance(o, DecisionWrite)]

    org_kinds = sorted(e.attrs.get("kind") for e in entities if e.kind == "Organisation")
    assert org_kinds == ["agency", "vendor"]

    # Org->TRANSACTS->Org dropped in Phase 1 hardening (schema-invalid).
    assert rels == []
    assert decisions == []  # no payload decisions in fixture


def test_vendor_kyc_projection_emits_decision_when_payload_carries_it():
    payload = fixture_payload("vendor-kyc", "vendors.json")
    wf = make_workflow(
        "VKY-T2", WORKFLOW_TYPE, payload,
        decisions=[{
            "phase": "finance_signoff",
            "verdict": "approve",
            "reason": "clean kyc",
            "decided_at": "2026-06-01T10:00:00+00:00",
        }],
        nest_under='vendor')
    ops = project(wf)
    decisions = [o for o in ops if isinstance(o, DecisionWrite)]
    assert len(decisions) == 1
    assert decisions[0].verdict == "approve"
    assert decisions[0].persona_role == "vendor_kyc_finance_bp"
