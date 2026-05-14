"""Pitch D4 — per-persona personality knobs.

Verifies:
  * loader gives every persona a fully-shaped ``personality`` dict
  * default-flavoured personae get the {balanced, medium, standard} trio
  * hand-flagged ``finance_bp`` carries {conservative, high, reluctant}
  * ``personality`` is in scope inside a ``decision_policy`` sandbox
"""
from __future__ import annotations

from api.server.services import persona_responder
from api.server.services.persona_responder import (
    _DEFAULT_PERSONALITY,
    _compile_decision_policy,
    _load_personae,
    _resolve_personality,
)


def test_loader_returns_personality_on_default_persona() -> None:
    personae = _load_personae()
    # ``analyst`` is one of the un-flagged personae; should carry defaults.
    assert "analyst" in personae, "expected analyst SKILL.md to load"
    p = personae["analyst"].personality
    assert p == _DEFAULT_PERSONALITY
    # All three keys must always be present, regardless of override status.
    for role, defn in personae.items():
        assert set(defn.personality.keys()) == set(_DEFAULT_PERSONALITY.keys()), (
            f"{role} personality is missing keys: {defn.personality}"
        )


def test_loader_respects_finance_bp_override() -> None:
    personae = _load_personae()
    assert "finance_bp" in personae
    assert personae["finance_bp"].personality == {
        "risk_appetite": "conservative",
        "thoroughness": "high",
        "escalation_style": "reluctant",
    }


def test_all_eight_demo_personae_overrides_present() -> None:
    expected = {
        "finance_bp": ("conservative", "high", "reluctant"),
        "cfo":        ("aggressive",   "medium", "quick"),
        "ap_clerk":   ("conservative", "high", "reluctant"),
        "controller": ("balanced",     "high", "standard"),
        "hr_bp":      ("balanced",     "medium", "standard"),
        "recruiter":  ("aggressive",   "low", "quick"),
        "gc":         ("conservative", "high", "reluctant"),
        "cpo":        ("aggressive",   "medium", "standard"),
    }
    personae = _load_personae()
    for role, (risk, thor, esc) in expected.items():
        assert role in personae, f"{role} SKILL.md missing"
        assert personae[role].personality == {
            "risk_appetite": risk,
            "thoroughness": thor,
            "escalation_style": esc,
        }, f"{role} personality wrong: {personae[role].personality}"


def test_resolve_personality_handles_missing_and_partial() -> None:
    assert _resolve_personality(None) == _DEFAULT_PERSONALITY
    assert _resolve_personality({}) == _DEFAULT_PERSONALITY
    partial = _resolve_personality({"risk_appetite": "aggressive"})
    assert partial["risk_appetite"] == "aggressive"
    assert partial["thoroughness"] == _DEFAULT_PERSONALITY["thoroughness"]
    assert partial["escalation_style"] == _DEFAULT_PERSONALITY["escalation_style"]
    # Unknown keys silently dropped; values coerced to str.
    full = _resolve_personality(
        {"risk_appetite": "conservative", "thoroughness": "low",
         "escalation_style": "quick", "spurious": "ignored"}
    )
    assert "spurious" not in full
    assert full == {"risk_appetite": "conservative", "thoroughness": "low",
                    "escalation_style": "quick"}


def test_personality_is_in_scope_inside_decision_policy() -> None:
    """A decision_policy can read `personality` from its local namespace."""
    src = (
        "if personality.get('risk_appetite') == 'conservative':\n"
        "    decision = 'reject'\n"
        "    reason = 'conservative on ' + str(context.get('value'))\n"
        "elif personality.get('risk_appetite') == 'aggressive':\n"
        "    decision = 'approve'\n"
        "    reason = 'aggressive go'\n"
        "else:\n"
        "    decision = 'escalate'\n"
        "    reason = 'balanced — defer'\n"
    )
    handler_conservative = _compile_decision_policy(
        "test_role", src,
        personality={"risk_appetite": "conservative",
                     "thoroughness": "high",
                     "escalation_style": "reluctant"},
    )
    handler_aggressive = _compile_decision_policy(
        "test_role", src,
        personality={"risk_appetite": "aggressive",
                     "thoroughness": "low",
                     "escalation_style": "quick"},
    )
    handler_default = _compile_decision_policy("test_role", src)

    assert handler_conservative({"value": 999})["decision"] == "reject"
    assert handler_aggressive({"value": 999})["decision"] == "approve"
    assert handler_default({"value": 1})["decision"] == "escalate"


def test_personality_dict_isolated_per_call() -> None:
    """A misbehaving policy mutating `personality` must not poison the next call."""
    src = (
        "personality['risk_appetite'] = 'mutated'\n"
        "decision = 'approve'\n"
        "reason = 'ok'\n"
    )
    handler = _compile_decision_policy(
        "test_role", src,
        personality={"risk_appetite": "balanced",
                     "thoroughness": "medium",
                     "escalation_style": "standard"},
    )
    handler({})
    # Re-call: the decision policy must still see 'balanced', not 'mutated'.
    src2 = (
        "decision = 'approve' if personality['risk_appetite'] == 'balanced' "
        "else 'reject'\n"
        "reason = personality['risk_appetite']\n"
    )
    handler2 = _compile_decision_policy(
        "test_role", src2,
        personality={"risk_appetite": "balanced",
                     "thoroughness": "medium",
                     "escalation_style": "standard"},
    )
    assert handler2({})["decision"] == "approve"


def test_persona_definition_default_personality_field() -> None:
    """The dataclass default keeps the `personality=` kwarg optional for
    callers that build PersonaDefinition synthetically (e.g. tests)."""
    p = persona_responder.PersonaDefinition(
        role="x", description="", workflow_label="?",
        external_event="e", decide=lambda c: {"decision": "approve", "reason": ""},
        skill_path=persona_responder.PERSONAE_DIR / "x" / "SKILL.md",
    )
    assert p.personality == {}
