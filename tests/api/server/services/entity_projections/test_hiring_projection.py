"""Test the hiring projection (pitch-a4)."""
from __future__ import annotations

from datetime import date

from api.server.services.entity_graph import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
)
from api.server.services.entity_projections.hiring import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def _hiring_payload(**overrides):
    base = {
        "candidate_id": "C-12345",
        "candidate_name": "Ada Lovelace",
        "role_family": "Data Engineering",
        "level_target": "Senior",
        "jurisdiction": "USA",
        "sourcing_channel": "LinkedIn",
    }
    base.update(overrides)
    return base


def test_hiring_projection_minimal_emits_person_org_asset_and_owns_rel():
    wf = make_workflow("HIRE-T1", WORKFLOW_TYPE, _hiring_payload())
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]
    decisions = [o for o in ops if isinstance(o, DecisionWrite)]

    kinds = {e.kind for e in entities}
    assert {"Person", "Organisation", "Asset"} <= kinds

    person = next(e for e in entities if e.kind == "Person")
    assert person.id == "PERSON-C-12345"
    assert person.attrs["name"] == "Ada Lovelace"

    org = next(e for e in entities if e.kind == "Organisation")
    assert org.id == "ORG-source-linkedin"
    assert org.attrs["kind"] == "sourcing-channel"

    asset = next(e for e in entities if e.kind == "Asset")
    assert asset.id == "ASSET-req-HIRE-T1"
    assert asset.attrs["kind"] == "requisition"
    assert asset.attrs["role_family"] == "Data Engineering"

    # Candidate OWNS the requisition.
    assert any(
        r.rel == "OWNS" and r.src_id == person.id and r.dst_id == asset.id
        for r in rels
    )

    # No decisions in payload → no DecisionWrite ops.
    assert decisions == []


def test_hiring_projection_falls_back_to_candidate_id_when_missing():
    wf = make_workflow(
        "HIRE-T2", WORKFLOW_TYPE, _hiring_payload(candidate_id=""),
    )
    ops = project(wf)
    person = next(o for o in ops if isinstance(o, EntityWrite) and o.kind == "Person")
    assert person.id == "PERSON-CANDIDATE-HIRE-T2"


def test_hiring_projection_emits_decisions_only_for_present_gates():
    decisions = [
        {
            "phase": "screening",
            "verdict": "approve",
            "reason": "strong CV",
            "decided_at": "2026-05-01T10:00:00",
            "persona_role": "recruiter",
        },
        {
            "phase": "offer",
            "verdict": "approve",
            "reason": "team consensus",
            "decided_at": "2026-05-15T10:00:00",
            "persona_role": "hr_bp",
        },
    ]
    wf = make_workflow(
        "HIRE-T3", WORKFLOW_TYPE, _hiring_payload(),
        decisions=decisions,
    )
    ops = project(wf)
    decisions_out = [o for o in ops if isinstance(o, DecisionWrite)]

    phases = {d.phase for d in decisions_out}
    assert phases == {"screening", "offer"}

    for d in decisions_out:
        # decided_on lists (person, asset, agency-org) for all four gates.
        assert d.decided_on == (
            "PERSON-C-12345",
            "ASSET-req-HIRE-T3",
            "ORG-source-linkedin",
        )


def test_hiring_projection_coerces_iso_start_date_to_date():
    wf = make_workflow(
        "HIRE-T4", WORKFLOW_TYPE,
        _hiring_payload(start_date="2026-09-01T00:00:00"),
    )
    ops = project(wf)
    person = next(o for o in ops if isinstance(o, EntityWrite) and o.kind == "Person")
    # ISO string in → datetime.date out (Kuzu has no implicit STRING→DATE cast).
    assert isinstance(person.attrs["employed_from"], date)
    assert person.attrs["employed_from"] == date(2026, 9, 1)
