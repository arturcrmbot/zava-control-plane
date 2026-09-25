"""Judgement profiles: parsing and validation of the SKILL.md ``judgement:`` block."""
from __future__ import annotations

import pytest
import yaml

from api.server.services.judgement.profiles import (
    GateFacts,
    ProfileError,
    parse_profile,
    resolve_facts,
)


def _adapter(context: dict) -> GateFacts:
    return GateFacts(texts={"agent_reasoning": "x"}, facts={}, recommendation="r", case="c")


def _resolver(ref: str):
    if ref != "verticals.test:adapter":
        raise ProfileError(f"unknown facts adapter {ref!r}")
    return _adapter


VALID = yaml.safe_load(
    """
character: "Thorough: you hold a case whenever the reasoning and the record disagree."
gates:
  app-fraud-reimbursement:
    facts: verticals.test:adapter
    reads:
      - {id: says_vulnerable, text: agent_reasoning, ask: "Does the text say the customer is vulnerable?"}
      - {id: says_no_marker, text: agent_reasoning, ask: "Does the text say no vulnerability marker is present?"}
      - {id: covers_no_action, text: agent_reasoning, ask: "Does the text say what happens if the bank does nothing?"}
    checks:
      - concern: "the reasoning says there is no marker, but the record shows one"
        when: {read: says_no_marker, is: yes, fact: customer_vulnerable, equals: true}
        unless: says_vulnerable
      - concern: "the reasoning does not say what happens if nothing is done"
        when: {read: covers_no_action, is: no}
        severity: minor
      - concern: "refusals always get a second pair of eyes"
        when: {fact: recommends_refusal, equals: true}
    decide:
      ask: "Given the findings, what should you do?"
      approve: "Approve it now"
      hold: "Hold it"
    min_lead: 0.35
"""
)


def _parse(raw=None):
    return parse_profile("fraud_decision_manager", raw if raw is not None else VALID, resolver=_resolver)


def test_parses_a_valid_profile() -> None:
    profile = _parse()
    gate = profile.gate("app-fraud-reimbursement")
    assert profile.role == "fraud_decision_manager"
    assert profile.character.startswith("Thorough")
    assert gate is not None and profile.gate("mule-account-investigation") is None
    assert gate.facts is _adapter and gate.facts_ref == "verticals.test:adapter"
    assert [r.id for r in gate.reads] == ["says_vulnerable", "says_no_marker", "covers_no_action"]
    assert gate.reads[0].question() == {"type": "noul", "instructions": "Does the text say the customer is vulnerable?"}
    first, second, third = gate.checks
    assert (first.read, first.read_is, first.fact, first.equals, first.unless, first.severity) == (
        "says_no_marker", "yes", "customer_vulnerable", True, "says_vulnerable", "serious")
    assert (second.read, second.read_is, second.fact, second.severity) == ("covers_no_action", "no", None, "minor")
    assert (third.read, third.fact, third.equals) == (None, "recommends_refusal", True)
    assert gate.decide.question() == {
        "type": "choice",
        "instructions": "Given the findings, what should you do?",
        "criteria": {"approve": "Approve it now", "hold": "Hold it"},
    }
    assert gate.min_lead == 0.35


def _broken(path: tuple, value):
    raw = yaml.safe_load(yaml.safe_dump(VALID))
    node = raw
    for key in path[:-1]:
        node = node[key]
    if value is _DELETE:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return raw


_DELETE = object()
_GATE = ("gates", "app-fraud-reimbursement")


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("gates",), {}, "gates"),
        (_GATE + ("facts",), "verticals.test:missing", "facts"),
        (_GATE + ("checks", 0, "when", "read"), "nope", "nope"),
        (_GATE + ("checks", 0, "unless"), "nope", "nope"),
        (_GATE + ("checks", 0, "when", "is"), "maybe", "is"),
        (_GATE + ("checks", 0, "severity"), "fatal", "severity"),
        (_GATE + ("checks", 2, "when"), {}, "when"),
        (_GATE + ("decide", "hold"), _DELETE, "hold"),
        (_GATE + ("min_lead",), 1.5, "min_lead"),
        (_GATE + ("reads", 1, "id"), "says_vulnerable", "duplicate"),
        (_GATE + ("reads", 0, "ask"), "", "ask"),
    ],
)
def test_rejects_broken_profiles(path, value, message) -> None:
    with pytest.raises(ProfileError, match=message) as info:
        _parse(_broken(path, value))
    assert "fraud_decision_manager" in str(info.value)


def test_rejects_too_many_reads() -> None:
    raw = _broken(_GATE + ("reads",), [
        {"id": f"r{i}", "text": "agent_reasoning", "ask": f"Question {i}?"} for i in range(9)
    ])
    raw["gates"]["app-fraud-reimbursement"]["checks"] = []
    with pytest.raises(ProfileError, match="at most 8"):
        _parse(raw)


def test_resolve_facts_only_imports_pack_or_platform_code() -> None:
    assert callable(resolve_facts("api.server.services.judgement.evidence:first_sentences"))
    with pytest.raises(ProfileError, match="verticals"):
        resolve_facts("os:getcwd")
    with pytest.raises(ProfileError, match="cannot import"):
        resolve_facts("verticals.nope:thing")
    with pytest.raises(ProfileError, match="module:function"):
        resolve_facts("verticals.banking.judgement_facts")
