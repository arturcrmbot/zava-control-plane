"""The judgement engine: how a persona reaches a verdict at a gate.

1. The ceiling is today's ``decision_policy`` result. Anything but an approval
   is kept as it is: Laya can only move a decision towards caution.
2. READ: Laya answers the profile's narrow questions about the gate's texts.
3. CHECK: code compares those readings with the record and names concerns.
4. A serious concern holds the case. With no concerns the case is approved.
   Only when every concern is minor does Laya weigh them in the persona's
   character (approve or hold): measured on this Mac, a single approve/hold
   question ignored some serious concerns, so it never gets to wave one
   through.
5. An unclear serious reading, or a minor-concern verdict without a clear
   lead, goes to the LLM deep review. A hold with nobody above to hand to
   also goes there.
6. If the deep review is spent or fails, or Laya is down, the ceiling applies
   and the record says the rules decided.

The approval payload the orchestrator validates is never rewritten: a judged
approval is the ceiling payload plus evidence fields.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from api.server.services.judgement import judgement_enabled
from api.server.services.judgement.deep_review import DeepReviewer, ReviewRequest, get_reviewer
from api.server.services.judgement.evidence import Judgement, Reading, Verdict
from api.server.services.judgement.laya_client import LayaClient, LayaUnavailable, get_client
from api.server.services.judgement.profiles import GateFacts, GateProfile, JudgementProfile

NO_CONCERNS = "No concerns were found in the agent's reasoning."


@dataclass
class Outcome:
    payload: dict[str, Any]
    judgement: Judgement | None
    hold: bool = False


def _min_lead(gate: GateProfile) -> float:
    raw = os.environ.get("JUDGEMENT_MIN_LEAD", "").strip()
    try:
        value = float(raw) if raw else gate.min_lead
    except ValueError:
        return gate.min_lead
    return value if 0.0 <= value <= 1.0 else gate.min_lead


def _with_evidence(ceiling: dict[str, Any], record: Judgement, **changes: Any) -> dict[str, Any]:
    summary = record.summary()
    return {
        **ceiling,
        **changes,
        "reason": summary,
        "authority_reason": ceiling.get("reason"),
        "decided_by": record.decided_by,
        "judgement_summary": summary,
    }


def _rules(ceiling: dict[str, Any], record: Judgement, reason: str) -> Outcome:
    record.decided_by = "rules"
    record.verdict = str(ceiling.get("decision") or "")
    record.fallback_reason = reason
    return Outcome(_with_evidence(ceiling, record), record)


async def _read(client: LayaClient, gate: GateProfile, facts: GateFacts, min_lead: float) -> tuple[list[Reading], float]:
    readings: list[Reading] = []
    latency = 0.0
    by_text: dict[str, list] = {}
    for spec in gate.reads:
        by_text.setdefault(spec.text, []).append(spec)
    for text_name, specs in by_text.items():
        text = (facts.texts.get(text_name) or "").strip()
        if not text:
            readings.extend(Reading(s.id, s.ask, text_name, None, 0.0, False) for s in specs)
            continue
        result = await client.ask({"text": text}, {s.id: s.question() for s in specs})
        latency += result.latency_ms
        for spec in specs:
            answer = result.answers[spec.id]
            p_yes = answer.probabilities.get("yes")
            readings.append(Reading(spec.id, spec.ask, text_name, p_yes, answer.lead, answer.lead >= min_lead))
    order = {spec.id: index for index, spec in enumerate(gate.reads)}
    readings.sort(key=lambda reading: order[reading.id])
    return readings, latency


def _check(gate: GateProfile, readings: list[Reading], facts: GateFacts) -> tuple[list[str], list[str], list[str]]:
    """Compare readings with the record: (all concerns, serious concerns, unclear)."""
    by_id = {reading.id: reading for reading in readings}
    concerns: list[str] = []
    serious: list[str] = []
    unclear: list[str] = []
    for check in gate.checks:
        if check.fact is not None and facts.facts.get(check.fact) != check.equals:
            continue
        if check.read is not None:
            reading = by_id[check.read]
            if not reading.clear:
                if check.severity == "serious":
                    unclear.append(f"could not tell whether {check.concern}")
                continue
            if reading.yes != (check.read_is == "yes"):
                continue
            if check.unless is not None:
                guard = by_id[check.unless]
                if not guard.clear or guard.yes:
                    if check.severity == "serious":
                        unclear.append(f"conflicting readings on whether {check.concern}")
                    continue
        concerns.append(check.concern)
        if check.severity == "serious":
            serious.append(check.concern)
    return concerns, serious, unclear


async def _judge(
    client: LayaClient,
    gate: GateProfile,
    persona_label: str,
    character: str,
    facts: GateFacts,
    concerns: list[str],
    min_lead: float,
) -> tuple[Verdict, float]:
    state = {
        "you_are": f"the {persona_label} at Zava Bank",
        "your_style": character,
        "recommendation": facts.recommendation,
        "concerns_found": "; ".join(concerns) if concerns else NO_CONCERNS,
    }
    result = await client.ask(state, {"decide": gate.decide.question()})
    answer = result.answers["decide"]
    return Verdict(answer.top, dict(answer.probabilities), answer.lead, min_lead), result.latency_ms


async def judge_gate(
    *,
    persona_role: str,
    persona_label: str,
    instructions: str,
    profile: JudgementProfile | None,
    context: dict[str, Any],
    ceiling: dict[str, Any],
    workflow_id: str | None,
    gate_phase: str | None,
    next_role: str | None,
    client: LayaClient | None = None,
    reviewer: DeepReviewer | None = None,
) -> Outcome:
    workflow_type = context.get("workflow_type") if isinstance(context, dict) else None
    gate = profile.gate(workflow_type) if profile is not None and judgement_enabled() else None
    if gate is None:
        return Outcome(ceiling, None)

    ceiling_decision = str(ceiling.get("decision") or "")
    record = Judgement(
        persona=persona_role, workflow_type=workflow_type, workflow_id=workflow_id,
        gate_phase=gate_phase, ceiling=ceiling_decision, decided_by="rules",
        verdict=ceiling_decision, character=profile.character, next_role=next_role,
    )
    if ceiling_decision != "approve":
        record.fallback_reason = f"the rules decided {ceiling_decision or 'nothing'}; judgement only reviews an approval"
        return Outcome(ceiling, record)

    client = client if client is not None else get_client()
    reviewer = reviewer if reviewer is not None else get_reviewer()
    min_lead = _min_lead(gate)
    try:
        facts = gate.facts(context)
        if not isinstance(facts, GateFacts):
            raise TypeError(f"{gate.facts_ref} returned {type(facts).__name__}, not GateFacts")
    except Exception as ex:  # a broken adapter must never block the gate
        return _rules(ceiling, record, f"the case could not be read: {ex}")
    if not client.available():
        return _rules(ceiling, record, "Laya unavailable" if client.enabled else "Laya is not configured")

    try:
        record.readings, read_ms = await _read(client, gate, facts, min_lead)
        record.laya_ms = read_ms
        record.concerns, record.serious, record.unclear = _check(gate, record.readings, facts)
        if record.concerns and not record.serious and not record.unclear:
            # Only minor concerns: whether they matter is the persona's call,
            # in its own character. Serious concerns and none need no weighing.
            record.judge, judge_ms = await _judge(
                client, gate, persona_label, profile.character, facts, record.concerns, min_lead
            )
            record.laya_ms += judge_ms
    except LayaUnavailable as ex:
        return _rules(ceiling, record, f"Laya unavailable: {ex}")

    if record.serious:
        # A serious concern Laya found in the reasoning holds the case: a
        # verified contradiction is never waved through on a soft verdict.
        holds, needs_review = True, False
    elif record.unclear:
        holds, needs_review = False, True
    elif record.judge is not None:
        holds, needs_review = record.judge.choice == "hold", not record.judge.clear
    else:
        holds, needs_review = False, False
    if not needs_review and not holds:
        record.decided_by, record.verdict = "laya", "approve"
        return Outcome(_with_evidence(ceiling, record), record)
    if not needs_review and holds and next_role:
        record.decided_by, record.verdict = "laya", "hold"
        return Outcome(_with_evidence(ceiling, record, decision="escalate"), record, hold=True)

    review = await reviewer.review(ReviewRequest(
        persona_role=persona_role, persona_label=persona_label, instructions=instructions,
        character=profile.character, facts=facts, concerns=list(record.concerns),
        unclear=list(record.unclear),
    ))
    if review is None:
        return _rules(ceiling, record, "the LLM budget for this hour is spent")
    record.deep_review = review
    if review.decision is None:
        return _rules(ceiling, record, f"the deep review failed: {review.error}")
    record.decided_by = "llm"
    if review.decision == "approve":
        record.verdict = "approve"
        return Outcome(_with_evidence(ceiling, record), record)
    if next_role:
        record.verdict = "hold"
        return Outcome(_with_evidence(ceiling, record, decision="escalate"), record, hold=True)
    record.verdict = "reject"
    return Outcome(_with_evidence(ceiling, record, decision="reject"), record)
