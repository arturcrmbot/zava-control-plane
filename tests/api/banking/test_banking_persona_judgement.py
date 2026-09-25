"""The persona responder decides banking gates by judgement when switched on."""
from __future__ import annotations

import asyncio
import importlib
import time
from types import SimpleNamespace

import pytest

from api.server.services.judgement.evidence import DeepReviewRecord
from api.server.services.judgement.laya_client import LayaAnswer, LayaResult
from api.server.world.runtime import SimulationRuntime
from api.shared.events import FleetEvent
from api.shared.types import Workflow
from api.shared.vertical_loader import active_runtime
from verticals.banking.fraud_constants import (
    FRAUD_COMMAND_TYPE,
    FRAUD_HITL_CATEGORY,
    FRAUD_HITL_EVENT,
    FRAUD_SCENARIO_STANDARD,
    FRAUD_SCENARIO_VULNERABLE,
)
from verticals.banking.fraud_constraints import admit_claim_options
from verticals.banking.worlds.scenario import ZavaBankWorld

pytestmark = pytest.mark.skipif(
    active_runtime().pack.name != "banking", reason="needs the banking pack active (ZAVA_VERTICAL=banking)"
)

REAL_STANDARD_REASONING = (
    "The only admitted option reimburses the customer in full, freezes recoverable funds in the "
    "beneficiary account, and raises the receiving provider's liability. No vulnerability flag is "
    "present, so no additional protections apply. Not acting would leave the customer uncompensated."
)
ROUTINE_READS = {"says_vulnerable": 0.08, "says_no_marker": 0.9, "argues_refusal": 0.16, "covers_no_action": 0.95}


class ScriptedLaya:
    enabled = True

    def __init__(self) -> None:
        self.reads = dict(ROUTINE_READS)
        self.verdicts = {"Fraud Decision Manager": {"approve": 0.9, "hold": 0.1},
                         "Financial Crime Lead": {"approve": 0.9, "hold": 0.1}}
        self.delay = 0.0
        self.calls = 0

    def available(self) -> bool:
        return True

    async def ask(self, state, questions):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        answers = {}
        for question_id, question in questions.items():
            if question["type"] == "noul":
                p = self.reads[question_id]
                answers[question_id] = LayaAnswer("noul", {"yes": p, "no": 1 - p}, "yes" if p >= 0.5 else "no", abs(2 * p - 1))
            else:
                probs = next(v for label, v in self.verdicts.items() if label in state["you_are"])
                top, low = sorted(probs.values(), reverse=True)
                answers[question_id] = LayaAnswer("choice", dict(probs), max(probs, key=probs.get), top - low)
        return LayaResult(answers, 40.0, 41.0)


class NoReview:
    def __init__(self) -> None:
        self.deadlines: list = []

    async def review(self, request, *, deadline=None):
        self.deadlines.append(deadline)
        return DeepReviewRecord("approve", "Consistent with the record.", 10.0, model="fake")


def _hitl_context(scenario: str, workflow_id: str, **extra) -> dict:
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    world.activate_scenario(scenario)
    observation = world.current_fraud_observation()
    admitted = [
        {"option_id": r.option.option_id, "value_gbp": r.option.value_gbp, "impact": r.option.impact}
        for r in admit_claim_options(observation) if r.feasible
    ]
    selected = admitted[0]
    return {
        "workflow_id": workflow_id,
        "instance_id": f"inst-{workflow_id}",
        "workflow_type": "app-fraud-reimbursement",
        "story_id": observation["story_id"],
        "claim_id": observation["claim"]["id"],
        "persona": "fraud_decision_manager",
        "external_event": FRAUD_HITL_EVENT,
        "phase": "Decide Reimbursement",
        "action": FRAUD_COMMAND_TYPE,
        "request": {"amount_gbp": selected["value_gbp"], "category": FRAUD_HITL_CATEGORY},
        "observation": observation,
        "admitted_options": admitted,
        "ranking": {"reasoning": REAL_STANDARD_REASONING, "ranked_option_ids": [selected["option_id"]]},
        "selected_option": selected,
        "selected_option_id": selected["option_id"],
        "decision_id": "SYN-APP-DECISION-001",
        "evidence_versions": observation["evidence_versions"],
        "authority": {"allowed": True},
        **extra,
    }


def _event(context: dict) -> FleetEvent:
    return FleetEvent(
        type="workflow.hitl.requested",
        workflow_id=context["workflow_id"],
        persona="fraud_decision_manager",
        phase="Decide Reimbursement",
        external_event=FRAUD_HITL_EVENT,
        instance_id=context["instance_id"],
        context=context,
    )


@pytest.fixture
def harness(monkeypatch):
    from api.server.services import persona_responder
    from api.server.services.judgement import engine

    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "*")
    monkeypatch.setenv("JUDGEMENT_ENABLED", "1")
    monkeypatch.delenv("DEMO_LOUD", raising=False)
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()
    persona_responder._JUDGING.clear()
    persona_responder._RECENTLY_JUDGED.clear()

    raised: list[tuple] = []

    async def fake_raise(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))
        return True

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", fake_raise)
    app_state = importlib.import_module("api.server.state").app_state
    events: list[FleetEvent] = []
    monkeypatch.setattr(app_state.bus, "emit", events.append)
    laya = ScriptedLaya()
    monkeypatch.setattr(engine, "get_client", lambda: laya)
    reviewer = NoReview()
    monkeypatch.setattr(engine, "get_reviewer", lambda: reviewer)
    contexts: list[dict] = []
    real_judge = engine.judge_gate

    async def spy(**kwargs):
        contexts.append(kwargs["context"])
        return await real_judge(**kwargs)

    monkeypatch.setattr(engine, "judge_gate", spy)
    yield SimpleNamespace(responder=persona_responder, raised=raised, events=events, laya=laya,
                          app_state=app_state, contexts=contexts, reviewer=reviewer)
    persona_responder._JUDGING.clear()
    persona_responder._RECENTLY_JUDGED.clear()


def _store(app_state, workflow_id: str) -> None:
    now = time.time()
    app_state.store.upsert_workflow(Workflow(
        id=workflow_id, type="app-fraud-reimbursement", status="awaiting_hitl",
        current_phase="Decide Reimbursement", created_at=now, sla_due_at=now + 3600,
        jurisdiction="SYN-UK-Zava", agency="Zava Bank", payload={},
    ))


def test_with_judgement_off_the_gate_is_decided_exactly_as_before(harness, monkeypatch) -> None:
    monkeypatch.setenv("JUDGEMENT_ENABLED", "0")
    context = _hitl_context(FRAUD_SCENARIO_STANDARD, "BAPP-J0")
    persona = harness.responder.PERSONA_DEFINITIONS["fraud_decision_manager"]
    expected = persona.decide(context)
    expected = {**expected, "persona": expected.get("persona") or "fraud_decision_manager",
                "decision_id": expected.get("decision_id")}
    asyncio.run(harness.responder._handle_hitl(_event(context)))
    assert [(name, payload) for _, name, payload in harness.raised] == [(FRAUD_HITL_EVENT, expected)]
    assert harness.laya.calls == 0
    assert not [e for e in harness.events if e.type == "persona.judgement"]


def test_a_clear_judgement_approves_with_evidence(harness) -> None:
    context = _hitl_context(FRAUD_SCENARIO_STANDARD, "BAPP-J1")
    _store(harness.app_state, "BAPP-J1")
    asyncio.run(harness.responder._handle_hitl(_event(context)))
    (_, name, payload), = harness.raised
    assert name == FRAUD_HITL_EVENT and payload["decision"] == "approve"
    assert payload["persona"] == "fraud_decision_manager" and payload["decided_by"] == "laya"
    assert payload["selected_option_id"] == context["selected_option_id"]
    assert payload["evidence_versions"] == context["evidence_versions"]
    judged = [e for e in harness.events if e.type == "persona.judgement"]
    assert judged and judged[0].decided_by == "laya"
    decided = [e for e in harness.events if e.type == "persona.decided"]
    assert decided and decided[0].decided_by == "laya"
    stashed = harness.app_state.store.get_workflow("BAPP-J1").payload["decisions"]
    assert stashed[-1]["decided_by"] == "laya" and stashed[-1]["judgement"]["verdict"] == "approve"


def test_a_hold_is_handed_to_the_financial_crime_lead_who_decides(harness) -> None:
    # The recorded standard reasoning, wrongly given for a vulnerable customer.
    context = _hitl_context(FRAUD_SCENARIO_VULNERABLE, "BAPP-J2", escalate_to="financial_crime_lead")
    _store(harness.app_state, "BAPP-J2")
    asyncio.run(harness.responder._handle_hitl(_event(context)))

    (_, name, payload), = harness.raised
    assert name == FRAUD_HITL_EVENT
    # The lead's own reading finds the same contradiction; at the top of the
    # chain the deep review decides, and the lead's approval says so.
    assert payload["persona"] == "financial_crime_lead" and payload["decision"] == "approve"
    assert payload["decided_by"] == "llm" and payload["reason"] == "Deep review: Consistent with the record."
    lead_context = harness.contexts[-1]
    assert lead_context["held_by"][0]["persona"] == "fraud_decision_manager"
    assert "record shows one" in lead_context["held_by"][0]["concerns"][0]
    decisions = harness.app_state.store.get_workflow("BAPP-J2").payload["decisions"]
    assert [(d["persona_role"], d["verdict"]) for d in decisions] == [
        ("fraud_decision_manager", "hold"), ("financial_crime_lead", "approve")]


def test_a_gate_is_judged_once_even_when_the_sweep_arrives_mid_judgement(harness) -> None:
    context = _hitl_context(FRAUD_SCENARIO_STANDARD, "BAPP-J3")
    harness.laya.delay = 0.2

    async def both() -> None:
        await asyncio.gather(harness.responder._handle_hitl(_event(context)),
                             harness.responder._handle_hitl(_event(context)))

    asyncio.run(both())
    assert len(harness.raised) == 1
    asyncio.run(harness.responder._handle_hitl(_event(context)))  # a sweep straight after
    assert len(harness.raised) == 1


def test_a_judged_gate_takes_no_fake_thinking_time(harness, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_LOUD", "1")
    context = _hitl_context(FRAUD_SCENARIO_STANDARD, "BAPP-J4")
    started = time.perf_counter()
    asyncio.run(harness.responder._handle_hitl(_event(context)))
    assert time.perf_counter() - started < 1.5
    assert len(harness.raised) == 1


def test_the_whole_chain_shares_one_deadline_well_inside_the_gate_timer(harness) -> None:
    # The orchestrator waits five minutes for this gate, hand-ups included.
    context = _hitl_context(FRAUD_SCENARIO_VULNERABLE, "BAPP-J5", escalate_to="financial_crime_lead")
    _store(harness.app_state, "BAPP-J5")
    started = time.monotonic()
    asyncio.run(harness.responder._handle_hitl(_event(context)))
    assert len(harness.raised) == 1
    deadlines = [d for d in harness.reviewer.deadlines]
    assert deadlines and len(set(deadlines)) == 1
    assert started + 60 < deadlines[0] <= started + 200


def test_a_busy_deep_review_queue_never_holds_a_gate_past_its_deadline(harness, monkeypatch) -> None:
    # Four vulnerable-customer gates at once, each ending in a deep review at
    # the lead, with reviews that take most of the time a gate has: the ones
    # that cannot start in time are decided by the rules, and spend nothing.
    from api.server.services.judgement import deep_review, engine

    class SlowLLM:
        async def run_session(self, **_):
            await asyncio.sleep(0.9)
            return SimpleNamespace(text='{"decision": "approve", "rationale": "Consistent with the record."}')

    budget = deep_review.Budget(6)
    reviewer = deep_review.DeepReviewer(budget=budget, runtime_factory=SlowLLM, model="fake")
    monkeypatch.setattr(engine, "get_reviewer", lambda: reviewer)
    monkeypatch.setattr(deep_review, "MIN_REVIEW_S", 0.5)
    monkeypatch.setenv("JUDGEMENT_GATE_DEADLINE_S", "2.0")
    contexts = [_hitl_context(FRAUD_SCENARIO_VULNERABLE, f"BAPP-Q{i}", escalate_to="financial_crime_lead")
                for i in range(4)]
    for context in contexts:
        _store(harness.app_state, context["workflow_id"])

    async def all_at_once() -> None:
        await asyncio.gather(*(harness.responder._handle_hitl(_event(context)) for context in contexts))

    started = time.perf_counter()
    asyncio.run(all_at_once())
    assert time.perf_counter() - started < 2.0
    assert len(harness.raised) == 4
    by = sorted(payload["decided_by"] for _, _, payload in harness.raised)
    assert by == ["llm", "llm", "rules", "rules"]
    late = [payload for _, _, payload in harness.raised if payload["decided_by"] == "rules"]
    assert all("no time left" in payload["reason"] for payload in late)
    assert all(payload["decision"] == "approve" for _, _, payload in harness.raised)
    assert budget.remaining() == 4
