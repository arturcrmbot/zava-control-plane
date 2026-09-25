"""Deep review: the budgeted LLM second look for unclear judgements."""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
from api.server.services.judgement import deep_review
from api.server.services.judgement.deep_review import (
    Budget,
    DeepReviewer,
    NoTimeToReview,
    ReviewRequest,
    parse_verdict,
)
from api.server.services.judgement.profiles import GateFacts


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _request() -> ReviewRequest:
    return ReviewRequest(
        persona_role="fraud_decision_manager",
        persona_label="Fraud Decision Manager",
        instructions="Approve only admitted options within delegation.",
        character="Thorough.",
        facts=GateFacts(
            texts={"agent_reasoning": "No vulnerability flag is present, so no additional protections apply."},
            facts={"customer_vulnerable": True},
            recommendation="Reimburse the customer in full (GBP 6,750)",
            case="The customer reports a scam of GBP 6,750. The customer carries a vulnerability marker.",
            prior_concerns=("an earlier reviewer found the reasoning inconsistent",),
        ),
        concerns=["the agent's reasoning says there is no vulnerability marker, but the record shows one"],
        unclear=[],
    )


def test_budget_allows_the_limit_per_rolling_hour() -> None:
    clock = _Clock()
    budget = Budget(2, clock=clock)
    assert [budget.try_consume(), budget.try_consume(), budget.try_consume()] == [True, True, False]
    assert budget.remaining() == 0
    clock.now += 3_601
    assert budget.remaining() == 2 and budget.try_consume() is True
    assert Budget(0, clock=clock).try_consume() is False


def _reviewer(runtime, budget=None) -> DeepReviewer:
    return DeepReviewer(budget=budget or Budget(5), runtime_factory=lambda: runtime, model="gpt-test")


def test_review_returns_the_llm_verdict_and_the_prompt_carries_the_case() -> None:
    runtime = FakeRuntime()
    runtime.canned_text = '{"decision": "hold", "rationale": "The reasoning contradicts the record. Hold it."}'
    record = asyncio.run(_reviewer(runtime).review(_request()))
    assert record is not None and record.decision == "hold"
    assert record.rationale == "The reasoning contradicts the record. Hold it."
    assert record.model == "gpt-test" and record.error is None and record.latency_ms >= 0
    prompt = runtime.last_prompt or ""
    for expected in (
        "Fraud Decision Manager",
        "The customer carries a vulnerability marker.",
        "Reimburse the customer in full (GBP 6,750)",
        "No vulnerability flag is present",
        "says there is no vulnerability marker, but the record shows one",
        "an earlier reviewer found the reasoning inconsistent",
        '"decision"',
    ):
        assert expected in prompt


def test_review_parses_fenced_json() -> None:
    runtime = FakeRuntime()
    runtime.canned_text = 'Here you go:\n```json\n{"decision": "Approve", "rationale": "Consistent."}\n```'
    record = asyncio.run(_reviewer(runtime).review(_request()))
    assert record is not None and record.decision == "approve"


@pytest.mark.parametrize("text", ["not json", '{"decision": "maybe", "rationale": "x"}', '{"decision": "approve"}'])
def test_unusable_answers_are_recorded_as_errors(text: str) -> None:
    runtime = FakeRuntime()
    runtime.canned_text = text
    record = asyncio.run(_reviewer(runtime).review(_request()))
    assert record is not None and record.decision is None and record.error


def test_a_runtime_failure_is_recorded_as_an_error() -> None:
    class Broken:
        async def run_session(self, **_: object):
            raise RuntimeError("rate limit, try again in 49 minutes")

    record = asyncio.run(_reviewer(Broken()).review(_request()))
    assert record is not None and record.decision is None and "rate limit" in (record.error or "")


def test_a_spent_budget_skips_the_llm() -> None:
    runtime = FakeRuntime()
    before = FakeRuntime.call_count
    assert asyncio.run(_reviewer(runtime, Budget(0)).review(_request())) is None
    assert FakeRuntime.call_count == before


def test_parse_verdict_rejects_missing_rationale() -> None:
    with pytest.raises(ValueError):
        parse_verdict('{"decision": "approve", "rationale": "  "}')


def test_the_prompt_says_what_a_hold_does_at_the_top_of_the_chain() -> None:
    from dataclasses import replace

    from api.server.services.judgement.deep_review import build_prompt

    first = build_prompt(replace(_request(), next_role_label=None))
    assert "Nobody above you can take this case" in first
    assert "goes back to the agent with your reasons" in first
    final = build_prompt(replace(_request(), next_role_label=None, final=True))
    assert "already re-assessed it once" in final and "declined" in final
    handed = build_prompt(replace(_request(), next_role_label="Financial Crime Lead"))
    assert "If you hold it, the case goes to the Financial Crime Lead" in handed
    assert "Nobody above you" not in handed


class _Slow:
    """An LLM session that takes a while, counting the sessions it ran."""

    def __init__(self, seconds: float) -> None:
        self.seconds, self.ran = seconds, 0

    async def run_session(self, **_: object):
        self.ran += 1
        await asyncio.sleep(self.seconds)
        return SimpleNamespace(text='{"decision": "approve", "rationale": "Consistent with the record."}')


def test_reviews_queued_behind_a_slow_one_give_up_before_the_gate_closes_and_spend_nothing(monkeypatch) -> None:
    monkeypatch.setattr(deep_review, "MIN_REVIEW_S", 0.45)
    runtime, budget = _Slow(0.3), Budget(6)
    reviewer = _reviewer(runtime, budget)

    async def three() -> list:
        deadline = time.monotonic() + 0.6
        return await asyncio.gather(
            *(reviewer.review(_request(), deadline=deadline) for _ in range(3)), return_exceptions=True)

    started = time.perf_counter()
    results = asyncio.run(three())
    assert time.perf_counter() - started < 0.55
    assert results[0].decision == "approve"
    assert [type(r) for r in results[1:]] == [NoTimeToReview, NoTimeToReview]
    assert runtime.ran == 1 and budget.remaining() == 5


def test_a_review_with_too_little_time_left_is_not_started() -> None:
    runtime, budget = _Slow(0.0), Budget(6)
    with pytest.raises(NoTimeToReview):
        asyncio.run(_reviewer(runtime, budget).review(_request(), deadline=time.monotonic() + 1.0))
    assert runtime.ran == 0 and budget.remaining() == 6


def test_a_running_review_is_cut_off_at_the_deadline(monkeypatch) -> None:
    monkeypatch.setattr(deep_review, "MIN_REVIEW_S", 0.1)
    started = time.perf_counter()
    record = asyncio.run(_reviewer(_Slow(5.0)).review(_request(), deadline=time.monotonic() + 0.3))
    assert time.perf_counter() - started < 1.0
    assert record is not None and record.decision is None and "TimeoutError" in (record.error or "")
