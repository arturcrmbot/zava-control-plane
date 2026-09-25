"""Judgement profiles: what a persona reads, how code checks it, how it decides.

A persona opts in with a ``judgement:`` block in its SKILL.md frontmatter::

    judgement:
      character: "Thorough: you hold a case whenever the reasoning and the record disagree."
      gates:
        app-fraud-reimbursement:              # the gate's workflow type
          facts: verticals.banking.judgement_facts:fraud_gate
          reads:                              # narrow yes/no questions for Laya
            - {id: says_no_marker, text: agent_reasoning, ask: "Does the text say ...?"}
          checks:                             # data, evaluated by code
            - concern: "the agent's reasoning says there is no marker, but the record shows one"
              when: {read: says_no_marker, is: yes, fact: customer_vulnerable, equals: true}
              unless: says_vulnerable         # a paired question; both yes means unclear
              severity: serious               # serious | minor
          decide: {ask: "...", approve: "...", hold: "..."}
          min_lead: 0.3

A check applies only when its fact condition holds. Its reading must then be
clear: an unclear reading makes a serious check unclear (the case goes to the
deep review) and skips a minor one.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable

DEFAULT_CHARACTER = "Balanced: you approve consistent cases and hold one when something is off."
DEFAULT_MIN_LEAD = 0.3
MAX_READS = 8
_ALLOWED_PREFIXES = ("verticals.", "api.")


class ProfileError(ValueError):
    """A persona's judgement block is malformed."""


@dataclass(frozen=True, slots=True)
class GateFacts:
    """What a pack's facts adapter extracts from one gate's context.

    ``texts`` are read by Laya; ``facts`` are compared by code; the rest is
    phrased for the judge question and the deep review.
    """

    texts: dict[str, str]
    facts: dict[str, Any]
    recommendation: str
    case: str
    prior_concerns: tuple[str, ...] = ()


FactsAdapter = Callable[[dict[str, Any]], GateFacts]


@dataclass(frozen=True, slots=True)
class ReadSpec:
    id: str
    text: str
    ask: str

    def question(self) -> dict[str, Any]:
        return {"type": "noul", "instructions": self.ask}


@dataclass(frozen=True, slots=True)
class CheckSpec:
    concern: str
    read: str | None
    read_is: str | None
    fact: str | None
    equals: Any
    unless: str | None
    severity: str


@dataclass(frozen=True, slots=True)
class DecideSpec:
    ask: str
    approve: str
    hold: str

    def question(self) -> dict[str, Any]:
        return {"type": "choice", "instructions": self.ask,
                "criteria": {"approve": self.approve, "hold": self.hold}}


@dataclass(frozen=True, slots=True)
class GateProfile:
    workflow_type: str
    facts_ref: str
    facts: FactsAdapter
    reads: tuple[ReadSpec, ...]
    checks: tuple[CheckSpec, ...]
    decide: DecideSpec
    min_lead: float


@dataclass(frozen=True, slots=True)
class JudgementProfile:
    role: str
    character: str
    gates: dict[str, GateProfile]

    def gate(self, workflow_type: str | None) -> GateProfile | None:
        return self.gates.get(workflow_type) if workflow_type else None


def resolve_facts(ref: str) -> FactsAdapter:
    module_name, sep, attr = str(ref).partition(":")
    if not sep or not module_name or not attr:
        raise ProfileError(f"facts adapter {ref!r} must be written module:function")
    if not module_name.startswith(_ALLOWED_PREFIXES):
        raise ProfileError(f"facts adapter {ref!r} must live under verticals. or api.")
    try:
        module = importlib.import_module(module_name)
    except ImportError as ex:
        raise ProfileError(f"cannot import facts adapter module {module_name!r}: {ex}") from ex
    adapter = getattr(module, attr, None)
    if not callable(adapter):
        raise ProfileError(f"facts adapter {ref!r} is not a callable")
    return adapter


def _text(value: Any, where: str, *, max_len: int = 400) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{where} must be a non-empty string")
    if len(value) > max_len:
        raise ProfileError(f"{where} is longer than {max_len} characters")
    return value.strip()


def _yes_no(value: Any, where: str) -> str:
    if value is True or (isinstance(value, str) and value.strip().lower() == "yes"):
        return "yes"
    if value is False or (isinstance(value, str) and value.strip().lower() == "no"):
        return "no"
    raise ProfileError(f"{where} must be yes or no, got {value!r}")


def _parse_reads(raw: Any, where: str) -> tuple[ReadSpec, ...]:
    if not isinstance(raw, list):
        raise ProfileError(f"{where} must be a list")
    if len(raw) > MAX_READS:
        raise ProfileError(f"{where} may hold at most {MAX_READS} questions")
    reads: list[ReadSpec] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        at = f"{where}[{index}]"
        if not isinstance(item, dict):
            raise ProfileError(f"{at} must be a mapping")
        read_id = _text(item.get("id"), f"{at}.id", max_len=60)
        if read_id in seen:
            raise ProfileError(f"{at}.id {read_id!r} is a duplicate")
        seen.add(read_id)
        reads.append(ReadSpec(read_id, _text(item.get("text"), f"{at}.text", max_len=60),
                              _text(item.get("ask"), f"{at}.ask", max_len=300)))
    return tuple(reads)


def _parse_checks(raw: Any, where: str, read_ids: set[str]) -> tuple[CheckSpec, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ProfileError(f"{where} must be a list")
    checks: list[CheckSpec] = []
    for index, item in enumerate(raw):
        at = f"{where}[{index}]"
        if not isinstance(item, dict):
            raise ProfileError(f"{at} must be a mapping")
        concern = _text(item.get("concern"), f"{at}.concern")
        when = item.get("when")
        if not isinstance(when, dict) or not ({"read", "fact"} & set(when)):
            raise ProfileError(f"{at}.when must name a read, a fact or both")
        read = when.get("read")
        if read is not None and read not in read_ids:
            raise ProfileError(f"{at}.when.read {read!r} is not one of the gate's reads")
        read_is = _yes_no(when.get("is", "yes"), f"{at}.when.is") if read is not None else None
        fact = when.get("fact")
        if fact is not None:
            fact = _text(fact, f"{at}.when.fact", max_len=60)
        unless = item.get("unless")
        if unless is not None and unless not in read_ids:
            raise ProfileError(f"{at}.unless {unless!r} is not one of the gate's reads")
        severity = item.get("severity", "serious")
        if severity not in ("serious", "minor"):
            raise ProfileError(f"{at}.severity must be serious or minor, got {severity!r}")
        checks.append(CheckSpec(concern, read, read_is, fact, when.get("equals", True), unless, severity))
    return tuple(checks)


def _parse_decide(raw: Any, where: str) -> DecideSpec:
    if not isinstance(raw, dict):
        raise ProfileError(f"{where} must be a mapping with ask, approve and hold")
    return DecideSpec(_text(raw.get("ask"), f"{where}.ask", max_len=300),
                      _text(raw.get("approve"), f"{where}.approve", max_len=200),
                      _text(raw.get("hold"), f"{where}.hold", max_len=200))


def _parse_min_lead(raw: Any, where: str) -> float:
    if raw is None:
        return DEFAULT_MIN_LEAD
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not 0.0 <= float(raw) <= 1.0:
        raise ProfileError(f"{where} must be a number between 0 and 1, got {raw!r}")
    return float(raw)


def parse_profile(
    role: str,
    raw: Any,
    *,
    resolver: Callable[[str], FactsAdapter] = resolve_facts,
) -> JudgementProfile:
    try:
        if not isinstance(raw, dict):
            raise ProfileError("judgement must be a mapping")
        character = raw.get("character")
        character = _text(character, "character") if character is not None else DEFAULT_CHARACTER
        gates_raw = raw.get("gates")
        if not isinstance(gates_raw, dict) or not gates_raw:
            raise ProfileError("gates must map at least one workflow type to a gate profile")
        gates: dict[str, GateProfile] = {}
        for workflow_type, gate_raw in gates_raw.items():
            where = f"gates.{workflow_type}"
            if not isinstance(gate_raw, dict):
                raise ProfileError(f"{where} must be a mapping")
            facts_ref = _text(gate_raw.get("facts"), f"{where}.facts", max_len=200)
            try:
                facts = resolver(facts_ref)
            except ProfileError as ex:
                raise ProfileError(f"{where}.facts: {ex}") from ex
            reads = _parse_reads(gate_raw.get("reads") or [], f"{where}.reads")
            checks = _parse_checks(gate_raw.get("checks"), f"{where}.checks", {r.id for r in reads})
            gates[str(workflow_type)] = GateProfile(
                workflow_type=str(workflow_type),
                facts_ref=facts_ref,
                facts=facts,
                reads=reads,
                checks=checks,
                decide=_parse_decide(gate_raw.get("decide"), f"{where}.decide"),
                min_lead=_parse_min_lead(gate_raw.get("min_lead"), f"{where}.min_lead"),
            )
        return JudgementProfile(role=role, character=character, gates=gates)
    except ProfileError as ex:
        raise ProfileError(f"persona {role!r} judgement: {ex}") from ex
