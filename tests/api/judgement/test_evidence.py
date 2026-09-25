"""Judgement evidence: every decision says who decided, what was read and why."""
from __future__ import annotations

import json

from api.server.services.judgement.evidence import (
    DeepReviewRecord,
    Judgement,
    Reading,
    Verdict,
)


def _judgement(**overrides) -> Judgement:
    base = dict(
        persona="fraud_decision_manager",
        workflow_type="app-fraud-reimbursement",
        workflow_id="BAPP-1",
        gate_phase="Decide Reimbursement",
        ceiling="approve",
        decided_by="laya",
        verdict="approve",
        concerns=[],
        unclear=[],
        readings=[Reading("says_no_marker", "Does the text say no marker is present?", "agent_reasoning", 0.9, 0.8, True)],
        judge=Verdict("approve", {"approve": 0.9, "hold": 0.1}, 0.8, 0.3),
        laya_ms=120.4,
        character="Thorough.",
    )
    base.update(overrides)
    return Judgement(**base)


def test_to_dict_is_json_safe_and_complete() -> None:
    record = _judgement(deep_review=DeepReviewRecord("approve", "Fine. Really fine. Extra.", 20_500.0, model="gpt-4.1"))
    data = json.loads(json.dumps(record.to_dict()))
    assert data["persona"] == "fraud_decision_manager"
    assert data["decided_by"] == "laya" and data["verdict"] == "approve" and data["ceiling"] == "approve"
    assert data["readings"][0] == {
        "id": "says_no_marker", "question": "Does the text say no marker is present?",
        "text": "agent_reasoning", "p_yes": 0.9, "lead": 0.8, "clear": True,
    }
    assert data["judge"] == {"choice": "approve", "probabilities": {"approve": 0.9, "hold": 0.1},
                             "lead": 0.8, "threshold": 0.3, "clear": True}
    assert data["deep_review"]["decision"] == "approve" and data["deep_review"]["model"] == "gpt-4.1"
    assert data["laya_ms"] == 120.4
    assert data["summary"] == record.summary()


def test_summary_for_a_clear_approval() -> None:
    assert _judgement().summary() == "Approved after reading the agent's reasoning: no concerns found."


def test_summary_for_a_hold_names_the_concerns_and_the_hand_off() -> None:
    record = _judgement(
        verdict="hold",
        concerns=["the agent's reasoning says there is no vulnerability marker, but the record shows one"],
        next_role="financial_crime_lead",
    )
    assert record.summary() == (
        "Held for a closer look: the agent's reasoning says there is no vulnerability "
        "marker, but the record shows one. Handed to the Financial crime lead."
    )


def test_summary_for_an_approval_despite_minor_concerns() -> None:
    record = _judgement(concerns=["the agent does not say what happens if the bank does nothing"])
    assert record.summary() == (
        "Approved despite: the agent does not say what happens if the bank does nothing."
    )


def test_summary_for_a_deep_review_keeps_two_sentences() -> None:
    record = _judgement(
        decided_by="llm",
        verdict="reject",
        deep_review=DeepReviewRecord("hold", "The reasoning contradicts the record. The customer is vulnerable. More detail here.", 21_000.0),
    )
    assert record.summary() == "Deep review: The reasoning contradicts the record. The customer is vulnerable."


def test_summary_for_rules() -> None:
    assert _judgement(decided_by="rules", fallback_reason="Laya unavailable").summary() == (
        "Decided by rules: Laya unavailable."
    )
    assert _judgement(decided_by="rules").summary() == "Decided by rules."


def test_summary_for_a_send_back() -> None:
    record = _judgement(
        decided_by="llm", verdict="send_back",
        deep_review=DeepReviewRecord("hold", "The reasoning contradicts the record. Correct it first.", 9_000.0),
    )
    assert record.summary() == "Sent back to the agent: The reasoning contradicts the record. Correct it first."
