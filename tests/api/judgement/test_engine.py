"""Judgement engine: ceiling, read, check, judge, deep review, rules."""
from __future__ import annotations

import asyncio
import itertools

import pytest
import yaml

from api.server.services.judgement.engine import judge_gate
from api.server.services.judgement.evidence import DeepReviewRecord
from api.server.services.judgement.laya_client import LayaAnswer, LayaResult, LayaUnavailable
from api.server.services.judgement.profiles import GateFacts, parse_profile

WORKFLOW = "app-fraud-reimbursement"


def _adapter(context: dict) -> GateFacts:
    if context.get("broken"):
        raise KeyError("observation")
    return GateFacts(
        texts={"agent_reasoning": context.get("reasoning", "The reasoning.")},
        facts={"customer_vulnerable": context.get("vulnerable", False),
               "recommends_refusal": context.get("refusal", False)},
        recommendation="Reimburse the customer in full (GBP 18,400)",
        case="The customer reports a scam of GBP 18,400.",
    )


PROFILE = parse_profile(
    "fraud_decision_manager",
    yaml.safe_load(
        """
character: "Thorough."
gates:
  app-fraud-reimbursement:
    facts: verticals.test:adapter
    reads:
      - {id: says_vulnerable, text: agent_reasoning, ask: "Does the text say the customer is vulnerable?"}
      - {id: says_no_marker, text: agent_reasoning, ask: "Does the text say no vulnerability marker is present?"}
      - {id: covers_no_action, text: agent_reasoning, ask: "Does the text say what happens if the bank does nothing?"}
    checks:
      - concern: "the agent's reasoning says there is no vulnerability marker, but the record shows one"
        when: {read: says_no_marker, is: yes, fact: customer_vulnerable, equals: true}
        unless: says_vulnerable
      - concern: "the agent does not say what happens if the bank does nothing"
        when: {read: covers_no_action, is: no}
        severity: minor
      - concern: "the recommendation refuses a fraud victim; refusals always get a second pair of eyes"
        when: {fact: recommends_refusal, equals: true}
    decide: {ask: "What should you do?", approve: "Approve it now", hold: "Hold it"}
    min_lead: 0.3
"""
    ),
    resolver=lambda ref: _adapter,
)

CEILING = {
    "decision": "approve",
    "reason": "within fraud_decision_manager delegation per matrix rule AUTH-x",
    "persona": "fraud_decision_manager",
    "selected_option_id": "SYN-APP-OPTION-REIMBURSE-FULL",
    "evidence_versions": {"SYN-CLAIM-0031": 2},
    "rationale": "within delegation",
}
ROUTINE_READS = {"says_vulnerable": 0.05, "says_no_marker": 0.9, "covers_no_action": 0.95}


class FakeLaya:
    enabled = True

    def __init__(self, reads=None, verdict=None, *, fail=False, available=True) -> None:
        self.reads = dict(ROUTINE_READS if reads is None else reads)
        self.verdict = verdict or {"approve": 0.9, "hold": 0.1}
        self.fail = fail
        self._available = available
        self.calls: list[tuple] = []

    def available(self) -> bool:
        return self._available

    async def ask(self, state, questions):
        self.calls.append((state, questions))
        if self.fail:
            raise LayaUnavailable("connection refused")
        answers = {}
        for question_id, question in questions.items():
            if question["type"] == "noul":
                p = self.reads[question_id]
                answers[question_id] = LayaAnswer("noul", {"yes": p, "no": 1 - p}, "yes" if p >= 0.5 else "no", abs(2 * p - 1))
            else:
                probs = dict(self.verdict)
                ordered = sorted(probs.values(), reverse=True)
                answers[question_id] = LayaAnswer("choice", probs, max(probs, key=probs.get), ordered[0] - ordered[1])
        return LayaResult(answers, 50.0, 51.0)


class FakeReviewer:
    def __init__(self, decision: str | None = "approve", *, spent=False, error=None) -> None:
        self.decision, self.spent, self.error = decision, spent, error
        self.requests: list = []

    async def review(self, request):
        self.requests.append(request)
        if self.spent:
            return None
        if self.error:
            return DeepReviewRecord(None, "", 12.0, error=self.error, model="fake")
        return DeepReviewRecord(self.decision, "The reasoning and the record disagree. Second sentence. Third.", 20_000.0, model="fake")


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    monkeypatch.setenv("JUDGEMENT_ENABLED", "1")
    monkeypatch.delenv("JUDGEMENT_MIN_LEAD", raising=False)


def _judge(context=None, *, ceiling=None, laya=None, reviewer=None, next_role="financial_crime_lead", profile=PROFILE):
    return asyncio.run(judge_gate(
        persona_role="fraud_decision_manager",
        persona_label="Fraud Decision Manager",
        instructions="Approve admitted options within delegation.",
        profile=profile,
        context={"workflow_type": WORKFLOW, **(context or {})},
        ceiling=dict(ceiling or CEILING),
        workflow_id="BAPP-1",
        gate_phase="Decide Reimbursement",
        next_role=next_role,
        client=laya or FakeLaya(),
        reviewer=reviewer or FakeReviewer(),
    ))


def test_flag_off_returns_the_ceiling_untouched(monkeypatch) -> None:
    monkeypatch.setenv("JUDGEMENT_ENABLED", "0")
    laya = FakeLaya()
    outcome = _judge(laya=laya)
    assert outcome.payload == CEILING and outcome.judgement is None and outcome.hold is False
    assert laya.calls == []


def test_no_profile_or_no_gate_returns_the_ceiling_untouched() -> None:
    assert _judge(profile=None).payload == CEILING
    outcome = _judge({"workflow_type": "mule-account-investigation"})
    assert outcome.payload == CEILING and outcome.judgement is None


@pytest.mark.parametrize("ceiling_decision", ["reject", "escalate"])
def test_laya_can_only_move_towards_caution(ceiling_decision: str) -> None:
    ceiling = {**CEILING, "decision": ceiling_decision, "reason": "outside delegation"}
    for reads, verdict, review in itertools.product(
        [ROUTINE_READS, {"says_vulnerable": 0.5, "says_no_marker": 0.5, "covers_no_action": 0.5}],
        [{"approve": 0.99, "hold": 0.01}, {"approve": 0.01, "hold": 0.99}],
        ["approve", "hold"],
    ):
        laya = FakeLaya(reads, verdict)
        outcome = _judge({"vulnerable": True}, ceiling=ceiling, laya=laya, reviewer=FakeReviewer(review))
        assert outcome.payload["decision"] == ceiling_decision
        assert outcome.payload["decision"] != "approve"
        assert laya.calls == []
        assert outcome.judgement is not None and outcome.judgement.decided_by == "rules"


def test_a_clear_approval_keeps_the_approval_payload_and_adds_evidence() -> None:
    laya = FakeLaya()
    outcome = _judge(laya=laya)
    record = outcome.judgement
    assert record is not None and record.decided_by == "laya" and record.verdict == "approve"
    for key in ("persona", "selected_option_id", "evidence_versions", "rationale", "decision"):
        assert outcome.payload[key] == CEILING[key]
    assert outcome.payload["decided_by"] == "laya"
    assert outcome.payload["reason"] == record.summary() == outcome.payload["judgement_summary"]
    assert outcome.payload["authority_reason"] == CEILING["reason"]
    assert outcome.hold is False and record.concerns == [] and record.unclear == []
    assert len(laya.calls) == 1 and record.judge is None  # nothing to weigh, so no verdict question
    read_state, read_questions = laya.calls[0]
    assert read_state == {"text": "The reasoning."} and set(read_questions) == set(ROUTINE_READS)


def test_a_contradiction_holds_and_hands_up() -> None:
    laya = FakeLaya({"says_vulnerable": 0.05, "says_no_marker": 0.95, "covers_no_action": 0.9},
                    {"approve": 0.2, "hold": 0.8})
    outcome = _judge({"vulnerable": True}, laya=laya)
    record = outcome.judgement
    assert outcome.hold is True and outcome.payload["decision"] == "escalate"
    assert record.decided_by == "laya" and record.verdict == "hold"
    assert record.concerns == ["the agent's reasoning says there is no vulnerability marker, but the record shows one"]
    assert record.serious == record.concerns
    assert "Handed to the Financial crime lead." in outcome.payload["reason"]
    assert len(laya.calls) == 1 and record.judge is None


def test_a_serious_concern_holds_even_when_laya_would_approve() -> None:
    laya = FakeLaya({"says_vulnerable": 0.05, "says_no_marker": 0.95, "covers_no_action": 0.9},
                    {"approve": 0.99, "hold": 0.01})
    outcome = _judge({"vulnerable": True}, laya=laya)
    assert outcome.hold is True and outcome.payload["decision"] == "escalate"
    assert outcome.judgement.judge is None


def test_minor_concerns_are_weighed_in_character() -> None:
    laya = FakeLaya({**ROUTINE_READS, "covers_no_action": 0.05}, {"approve": 0.1, "hold": 0.9})
    outcome = _judge(laya=laya)
    record = outcome.judgement
    assert record.serious == [] and record.concerns == ["the agent does not say what happens if the bank does nothing"]
    assert outcome.hold is True and record.decided_by == "laya" and record.judge.choice == "hold"
    judge_state, judge_questions = laya.calls[1]
    assert judge_state["your_style"] == "Thorough."
    assert judge_state["concerns_found"] == "the agent does not say what happens if the bank does nothing"
    assert judge_state["recommendation"] == "Reimburse the customer in full (GBP 18,400)"
    assert set(judge_questions["decide"]["criteria"]) == {"approve", "hold"}


@pytest.mark.parametrize(("review", "decision"), [("approve", "approve"), ("hold", "reject")])
def test_at_the_top_of_the_chain_the_deep_review_decides_a_hold(review: str, decision: str) -> None:
    reviewer = FakeReviewer(review)
    laya = FakeLaya({"says_vulnerable": 0.05, "says_no_marker": 0.95, "covers_no_action": 0.9},
                    {"approve": 0.2, "hold": 0.8})
    outcome = _judge({"vulnerable": True}, laya=laya, reviewer=reviewer, next_role=None)
    assert outcome.payload["decision"] == decision and outcome.hold is False
    assert outcome.judgement.decided_by == "llm"
    assert outcome.payload["reason"] == "Deep review: The reasoning and the record disagree. Second sentence."
    request = reviewer.requests[0]
    assert request.concerns == outcome.judgement.concerns and request.persona_label == "Fraud Decision Manager"


def test_a_deep_review_hold_below_the_top_still_hands_up() -> None:
    laya = FakeLaya({"says_vulnerable": 0.05, "says_no_marker": 0.6, "covers_no_action": 0.9})
    outcome = _judge({"vulnerable": True}, laya=laya, reviewer=FakeReviewer("hold"))
    assert outcome.hold is True and outcome.payload["decision"] == "escalate"
    assert outcome.judgement.decided_by == "llm" and outcome.judgement.verdict == "hold"


def test_an_unclear_serious_reading_goes_to_the_deep_review_and_falls_back_to_rules() -> None:
    reviewer = FakeReviewer(spent=True)
    laya = FakeLaya({"says_vulnerable": 0.05, "says_no_marker": 0.6, "covers_no_action": 0.9})
    outcome = _judge({"vulnerable": True}, laya=laya, reviewer=reviewer)
    record = outcome.judgement
    assert reviewer.requests and record.unclear
    assert record.decided_by == "rules" and "budget" in (record.fallback_reason or "")
    assert outcome.payload["decision"] == "approve" and outcome.payload["decided_by"] == "rules"
    assert outcome.payload["selected_option_id"] == CEILING["selected_option_id"]


def test_a_small_verdict_lead_goes_to_the_deep_review() -> None:
    reviewer = FakeReviewer("approve")
    laya = FakeLaya({**ROUTINE_READS, "covers_no_action": 0.05}, {"approve": 0.55, "hold": 0.45})
    outcome = _judge(laya=laya, reviewer=reviewer)
    assert reviewer.requests and outcome.judgement.decided_by == "llm"
    assert outcome.payload["decision"] == "approve"


def test_paired_readings_that_both_say_yes_are_unclear_not_a_concern() -> None:
    reviewer = FakeReviewer("approve")
    laya = FakeLaya({"says_vulnerable": 0.97, "says_no_marker": 0.99, "covers_no_action": 0.9})
    outcome = _judge({"vulnerable": True}, laya=laya, reviewer=reviewer)
    assert outcome.judgement.concerns == []
    assert outcome.judgement.unclear and "conflicting" in outcome.judgement.unclear[0]
    assert reviewer.requests and outcome.payload["decision"] == "approve"


def test_minor_checks_are_raised_only_when_clear() -> None:
    unclear_minor = _judge(laya=FakeLaya({**ROUTINE_READS, "covers_no_action": 0.55}))
    assert unclear_minor.judgement.unclear == [] and unclear_minor.judgement.decided_by == "laya"
    clear_minor = _judge(laya=FakeLaya({**ROUTINE_READS, "covers_no_action": 0.05}))
    assert clear_minor.judgement.concerns == ["the agent does not say what happens if the bank does nothing"]


def test_a_fact_only_check_raises_its_concern_without_a_reading() -> None:
    laya = FakeLaya(verdict={"approve": 0.1, "hold": 0.9})
    outcome = _judge({"refusal": True}, laya=laya)
    assert "refusals always get a second pair of eyes" in outcome.judgement.concerns[0]
    assert outcome.hold is True


@pytest.mark.parametrize(
    ("laya", "context", "reason"),
    [
        (FakeLaya(available=False), {}, "Laya"),
        (FakeLaya(fail=True), {}, "Laya unavailable"),
        (FakeLaya(), {"broken": True}, "could not be read"),
    ],
)
def test_laya_or_adapter_failure_falls_back_to_the_rules(laya, context, reason) -> None:
    outcome = _judge(context, laya=laya)
    assert outcome.payload["decision"] == "approve" and outcome.judgement.decided_by == "rules"
    assert reason in outcome.judgement.fallback_reason


def test_a_failed_deep_review_falls_back_to_the_rules() -> None:
    outcome = _judge({"vulnerable": True},
                     laya=FakeLaya({"says_vulnerable": 0.05, "says_no_marker": 0.6, "covers_no_action": 0.9}),
                     reviewer=FakeReviewer(error="RuntimeError: rate limit"))
    assert outcome.judgement.decided_by == "rules"
    assert "deep review failed" in outcome.judgement.fallback_reason
    assert outcome.judgement.deep_review is not None and outcome.judgement.deep_review.error


def test_the_min_lead_can_be_raised_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("JUDGEMENT_MIN_LEAD", "0.9")
    reviewer = FakeReviewer("approve")
    laya = FakeLaya({"says_vulnerable": 0.01, "says_no_marker": 0.99, "covers_no_action": 0.02},
                    {"approve": 0.9, "hold": 0.1})
    _judge(laya=laya, reviewer=reviewer)
    assert reviewer.requests
