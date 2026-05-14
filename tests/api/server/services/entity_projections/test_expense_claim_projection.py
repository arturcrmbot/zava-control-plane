"""Test the expense-claim projection (pitch-a4)."""
from __future__ import annotations

from datetime import date

from api.server.services.entity_graph import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
)
from api.server.services.entity_projections.expense_claim import (
    project, WORKFLOW_TYPE,
)

from ._helpers import make_workflow


def _claim_payload(**overrides):
    base = {
        "claim_id": "CLM-9999",
        "employee_id": "EMP-0042",
        "submitted_at": "2026-04-15T10:30:00",
        "currency": "GBP",
        "category": "meals",
        "vendor": "The Ivy",
        "amount": 33.81,
    }
    base.update(overrides)
    return base


def test_expense_claim_projection_minimal_emits_person_money_period():
    wf = make_workflow("EXP-T1", WORKFLOW_TYPE, _claim_payload(), nest_under="claim")
    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]
    decisions = [o for o in ops if isinstance(o, DecisionWrite)]

    kinds = {e.kind for e in entities}
    assert {"Person", "Money", "Period"} <= kinds

    person = next(e for e in entities if e.kind == "Person")
    assert person.id == "PERSON-EMP-0042"

    money = next(e for e in entities if e.kind == "Money")
    assert money.id == "MONEY-CLAIM-EXP-T1"
    assert money.attrs["kind"] == "expense-claim"
    assert money.attrs["amount"] == 33.81
    assert money.attrs["currency"] == "GBP"

    period = next(e for e in entities if e.kind == "Period")
    assert period.id == "PERIOD-2026-Q2"

    assert any(r.rel == "BELONGS_TO" and r.src_id == money.id and r.dst_id == period.id
               for r in rels)

    # No decisions in the payload → no DecisionWrite ops.
    assert decisions == []


def test_expense_claim_projection_falls_back_to_claimant_id():
    wf = make_workflow(
        "EXP-T2", WORKFLOW_TYPE, _claim_payload(employee_id=""), nest_under="claim",
    )
    ops = project(wf)
    person = next(o for o in ops if isinstance(o, EntityWrite) and o.kind == "Person")
    assert person.id == "PERSON-claimant-EXP-T2"


def test_expense_claim_projection_emits_decision_only_when_present():
    decisions = [
        {
            "phase": "Arbitrate",
            "verdict": "approve",
            "reason": "within policy",
            "decided_at": "2026-07-02T09:00:00",
            "persona_role": "ssc_reviewer",
        },
    ]
    wf = make_workflow(
        "EXP-T3", WORKFLOW_TYPE, _claim_payload(), nest_under="claim",
        decisions=decisions,
    )
    ops = project(wf)
    decisions_out = [o for o in ops if isinstance(o, DecisionWrite)]

    # Only Arbitrate is present in payload — Notify is skipped.
    phases = {d.phase for d in decisions_out}
    assert phases == {"Arbitrate"}

    arb = decisions_out[0]
    # decided_on must list (person, money, period) — all three shards.
    assert arb.decided_on == ("PERSON-EMP-0042", "MONEY-CLAIM-EXP-T3", "PERIOD-2026-Q3")


def test_expense_claim_projection_coerces_iso_submitted_at_to_date():
    wf = make_workflow(
        "EXP-T4", WORKFLOW_TYPE,
        _claim_payload(submitted_at="2026-09-01T08:00:00"),
        nest_under="claim",
    )
    ops = project(wf)
    person = next(o for o in ops if isinstance(o, EntityWrite) and o.kind == "Person")
    # Date coercion: ISO string in → datetime.date out (Kuzu has no
    # implicit STRING→DATE cast).
    assert isinstance(person.attrs["claim_submitted_on"], date)
    assert person.attrs["claim_submitted_on"] == date(2026, 9, 1)

    period = next(o for o in ops if isinstance(o, EntityWrite) and o.kind == "Period")
    assert period.id == "PERIOD-2026-Q3"
