"""Tests for plain-language translator (spec §9 polish item g, v1.1)."""
from __future__ import annotations

from api.server.services.plain_language import (
    persona_title,
    verdict_label,
    scope_label,
    pretty_entity_id,
    pretty_action,
    pretty_decision,
)


def test_persona_title_known_and_unknown():
    assert persona_title("cfo") == "CFO"
    assert persona_title("weird_role") == "Weird Role"
    assert persona_title(None) == ""
    assert persona_title("") == ""


def test_verdict_label_known_and_unknown():
    assert verdict_label("freeze") == "Freeze"
    assert verdict_label("weird") == "Weird"
    assert verdict_label(None) == ""


def test_scope_label_known_and_unknown():
    assert scope_label("po") == "purchase orders"
    assert scope_label("weird") == "weird"
    assert scope_label(None) == ""


def test_pretty_entity_id():
    assert pretty_entity_id("BRAND-aurora") == "Aurora"
    assert pretty_entity_id("ORG-vendor-acme-co") == "Acme Co"
    assert pretty_entity_id("FX:EUR/GBP") == "EUR/GBP"
    assert pretty_entity_id("DEPT:Finance") == "Finance"
    assert pretty_entity_id("UNKNOWN-xyz") == "UNKNOWN-xyz"
    assert pretty_entity_id(None) == ""


def test_pretty_action_full_example():
    action = {
        "verdict": "freeze",
        "decided_on": ["BRAND-aurora"],
        "attributes": {"scope": "po", "expiry_days": 14},
        "label": "fallback",
    }
    out = pretty_action(action)
    assert out.startswith("Freeze Aurora purchase orders")
    assert "(14 days)" in out


def test_pretty_action_falls_back_to_label_when_minimal():
    assert pretty_action({"label": "fallback text"}) == "fallback text"


def test_pretty_decision_policy_set():
    decision = {
        "phase": "policy_set",
        "persona_role": "cfo",
        "verdict": "freeze",
        "decided_on": ["BRAND-aurora"],
        "attributes": {"scope": "po", "expiry_days": 14},
    }
    out = pretty_decision(decision)
    assert "CFO Policy: Freeze Aurora purchase orders" in out
    assert "(14d)" in out


def test_pretty_decision_other_phase():
    decision = {
        "phase": "approve",
        "persona_role": "ap_clerk",
        "verdict": "approve",
        "decided_on": ["INV-7841"],
    }
    out = pretty_decision(decision)
    assert "AP Clerk approved" in out
    assert "INV-7841" in out
