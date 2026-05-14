"""Pitch I6 — persona experience attribute unit tests."""
from __future__ import annotations

import pytest

from api.server.services import persona_experience


@pytest.fixture(autouse=True)
def _clean():
    persona_experience.reset()
    yield
    persona_experience.reset()


def test_record_increments_per_role_per_domain():
    for _ in range(3):
        persona_experience.record_decision("controller", "ap_invoice")
    persona_experience.record_decision("controller", "expense_claim")
    persona_experience.record_decision("cfo", "ap_invoice")

    assert persona_experience.experience_score("controller", "ap_invoice") == 3
    assert persona_experience.experience_score("controller", "expense_claim") == 1
    assert persona_experience.experience_score("cfo", "ap_invoice") == 1
    assert persona_experience.experience_score("cfo", "expense_claim") == 0


def test_record_ignores_blanks():
    persona_experience.record_decision(None, "d")
    persona_experience.record_decision("r", None)
    persona_experience.record_decision("", "d")
    persona_experience.record_decision("r", "")
    assert persona_experience.snapshot() == {}


def test_experience_score_for_unknown_is_zero():
    assert persona_experience.experience_score("nobody", "nowhere") == 0
    assert persona_experience.experience_score(None, None) == 0


def test_snapshot_returns_independent_copies():
    persona_experience.record_decision("controller", "ap_invoice")
    snap = persona_experience.snapshot()
    snap["controller"]["ap_invoice"] = 999
    # Mutating the snapshot must not bleed back.
    assert persona_experience.experience_score("controller", "ap_invoice") == 1
