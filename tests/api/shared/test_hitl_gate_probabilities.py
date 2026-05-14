"""Pitch-c6: long-tail HITL persona probability fields on HitlGate.

Validates that the dataclass carries the new fields with safe defaults
and that the tactical hand-set values from the brief are persisted on
the listed gates.
"""
from __future__ import annotations

from api.shared.domains import DOMAINS, HitlGate


def test_hitl_gate_has_new_probability_fields():
    g = HitlGate("p", "e", "role")
    assert g.wait_probability == 0.0
    assert g.sick_probability == 0.0
    assert g.holiday_probability == 0.0
    assert g.timeout_probability == 0.0
    assert g.override_probability == 0.0


def test_hitl_gate_accepts_keyword_overrides():
    g = HitlGate(
        "p", "e", "role",
        wait_probability=0.1,
        sick_probability=0.05,
        holiday_probability=0.05,
        timeout_probability=0.1,
        override_probability=0.05,
    )
    assert g.sick_probability == 0.05
    assert g.holiday_probability == 0.05
    assert g.timeout_probability == 0.1
    assert g.override_probability == 0.05


def _find_gate(workflow_type: str, persona: str, external_event: str) -> HitlGate:
    d = DOMAINS[workflow_type]
    for g in d.hitl_gates:
        if g.persona == persona and g.external_event == external_event:
            return g
    raise AssertionError(
        f"no gate persona={persona!r} event={external_event!r} in {workflow_type}"
    )


def test_ap_clerk_gate_has_sick_and_timeout():
    g = _find_gate("ap-invoice", "ap_clerk", "ap_invoice_processing_decision")
    assert g.sick_probability == 0.05
    assert g.timeout_probability == 0.10


def test_controller_gate_has_holiday():
    g = _find_gate("ap-invoice", "controller", "controller_signoff_decision")
    assert g.holiday_probability == 0.05


def test_cfo_gate_has_override():
    # board-prep board_signoff is a cfo gate.
    g = _find_gate("board-prep", "cfo", "board_pack_decision")
    assert g.override_probability == 0.05


def test_line_manager_gate_has_sick_and_holiday():
    g = _find_gate("travel-preapproval", "line_manager", "manager_approval_decision")
    assert g.sick_probability == 0.10
    assert g.holiday_probability == 0.05


def test_recruiter_gate_has_override():
    g = _find_gate("hiring", "recruiter", "interview_invite")
    assert g.override_probability == 0.10


def test_most_gates_have_zero_long_tail_defaults():
    # Tactical handful only — make sure we did NOT blanket-set values.
    nonzero = 0
    total = 0
    for d in DOMAINS.values():
        for g in d.hitl_gates:
            total += 1
            if any((
                g.sick_probability,
                g.holiday_probability,
                g.timeout_probability,
                g.override_probability,
            )):
                nonzero += 1
    assert total > 0
    assert nonzero <= 8, (
        f"expected only a tactical handful of gates with long-tail "
        f"probabilities; got {nonzero}/{total}"
    )
