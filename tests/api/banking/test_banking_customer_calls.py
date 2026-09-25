"""Phase 3: the presenter steers. A customer calls about any payment."""
from __future__ import annotations

import asyncio

import pytest

from api.server.services.judgement.laya_client import LayaAnswer, LayaResult, LayaUnavailable
from api.server.world.runtime import SimulationRuntime
from verticals.banking.fraud_constants import FRAUD_SENSOR_ID
from verticals.banking.worlds.scenario import ZavaBankWorld
from verticals.banking.worlds.statements import StatementReading, read_statement, rules_reading

STATEMENT = ("Someone rang saying they were from Zava Bank's fraud team and told me to move my savings to a "
             "safe account. Since my husband died last year I handle the money alone.")


class _Client:
    enabled = True

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.states: list = []

    def available(self) -> bool:
        return True

    async def ask(self, state, questions):
        self.states.append(state)
        if self.fail:
            raise LayaUnavailable("down")
        answers = {"scam_type": LayaAnswer("choice", {"bank_impersonation": 0.9, "romance": 0.1},
                                           "bank_impersonation", 0.8)}
        for question_id in questions:
            if question_id != "scam_type":
                p = 0.9 if question_id == "death" else 0.05
                answers[question_id] = LayaAnswer("noul", {"yes": p, "no": 1 - p}, "yes" if p >= 0.5 else "no", abs(2 * p - 1))
        return LayaResult(answers, 50.0, 51.0)


def test_laya_reads_the_scam_and_the_circumstances() -> None:
    client = _Client()
    reading = asyncio.run(read_statement(STATEMENT, client=client))
    assert (reading.scam_type, reading.read_by) == ("bank_impersonation", "laya")
    assert reading.cues == ["bereavement"]
    assert len(client.states) == 1 and client.states[0] == {"customer_statement": STATEMENT}


def test_the_rules_read_when_laya_is_down() -> None:
    reading = asyncio.run(read_statement(STATEMENT, client=_Client(fail=True)))
    assert reading.read_by == "rules" and reading.scam_type == "bank_impersonation"
    assert "bereavement" in reading.cues
    assert rules_reading("I paid a kitchen fitter but the work is poor").scam_type == "not_scam"


def _world() -> ZavaBankWorld:
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    return world


def _settled_payment(world: ZavaBankWorld, *, vulnerable: bool) -> str:
    for payment in world.payments.values():
        account = world.accounts[payment.from_account_id]
        customer = world.customers[account.customer_id]
        if payment.status == "settled" and customer.vulnerability_flag is vulnerable and customer.status == "active":
            return payment.id
    raise AssertionError("no settled payment")


def test_a_customer_call_raises_a_claim_on_that_payment() -> None:
    world = _world()
    payment_id = _settled_payment(world, vulnerable=False)
    payment = world.payments[payment_id]
    reading = StatementReading("bank_impersonation", 0.8, ["bereavement"], "laya")
    sensor = world.customer_calls(payment_id, STATEMENT, reading.to_dict())
    assert sensor.type == "sensor.tripped" and sensor.actor_id == FRAUD_SENSOR_ID
    claim = world.fraud_claims[sensor.payload["claim_id"]]
    assert (claim.payment_id, claim.amount_gbp, claim.beneficiary_id) == (payment_id, payment.amount_gbp, payment.to_beneficiary_id)
    # The record decides vulnerability, not the customer's words.
    assert claim.vulnerability_flag is False and claim.specific_warning_ignored is False
    assert payment.status == "disputed"
    observation = world.observation_for_claim(claim.id)
    assert observation["customer_statement"] == {"text": STATEMENT, **reading.to_dict()}
    with pytest.raises(ValueError, match="already"):
        world.customer_calls(payment_id, STATEMENT, None)


def test_a_vulnerable_customer_on_record_stays_protected() -> None:
    world = _world()
    payment_id = _settled_payment(world, vulnerable=True)
    sensor = world.customer_calls(payment_id, "I was told to move my money.", None)
    assert world.fraud_claims[sensor.payload["claim_id"]].vulnerability_flag is True


def test_claims_without_a_call_carry_no_statement() -> None:
    world = _world()
    claim_id = world.raise_claim("any").payload["claim_id"]
    assert "customer_statement" not in world.observation_for_claim(claim_id)


@pytest.mark.parametrize("statement", ["", "   ", "x" * 1_201])
def test_a_call_needs_a_short_statement(statement: str) -> None:
    world = _world()
    with pytest.raises(ValueError, match="statement"):
        world.customer_calls(_settled_payment(world, vulnerable=False), statement, None)


# --- Routes: a customer calls; ask the persona ------------------------------------------------

import time  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from api.server.services.event_bus import EventBus  # noqa: E402
from api.server.world.service import ActorWorldService  # noqa: E402


def test_call_scenario_runs_a_world_method_and_publishes_it(monkeypatch) -> None:
    from api.shared.vertical_loader import active_runtime

    monkeypatch.setenv("ZAVA_VERTICAL", "banking")
    active_runtime.cache_clear()
    try:
        bus = EventBus()
        published: list = []
        bus.on_any(published.append)
        service = ActorWorldService.for_world("banking", seed=42, bus=bus)
        payment_id = _settled_payment(service.scenario, vulnerable=False)
        event = service.call_scenario("customer_calls", payment_id, "I was told to move my money.", None)
    finally:
        active_runtime.cache_clear()
    assert event.type == "sensor.tripped"
    assert any(e.type == "world.sensor.tripped" for e in published)


def test_the_customer_calls_route_reads_the_statement_then_raises_the_claim(monkeypatch) -> None:
    from api.server.routes import world as world_routes
    from api.server.state import app_state

    world = _world()
    payment_id = _settled_payment(world, vulnerable=False)
    reads: list[str] = []

    async def read(statement: str):
        reads.append(statement)
        return StatementReading("bank_impersonation", 0.8, ["bereavement"], "laya")

    monkeypatch.setattr(world, "read_customer_statement", read)
    service = SimpleNamespace(scenario=world, call_scenario=lambda name, *args: getattr(world, name)(*args))
    monkeypatch.setattr(app_state, "world_service", service, raising=False)
    result = asyncio.run(world_routes.customer_calls(world_routes.CustomerCall(payment_id=payment_id, statement=STATEMENT)))
    assert result["ok"] is True and reads == [STATEMENT]
    assert result["reading"] == {"scam_type": "bank_impersonation", "scam_lead": 0.8, "cues": ["bereavement"], "read_by": "laya"}
    assert world.observation_for_claim(result["claim_id"])["customer_statement"]["cues"] == ["bereavement"]
    again = asyncio.run(world_routes.customer_calls(world_routes.CustomerCall(payment_id=payment_id, statement=STATEMENT)))
    assert again["ok"] is False and "already" in again["error"]


def _judged_workflow(app_state, workflow_id: str, reasoning: str, vulnerable: bool) -> None:
    from api.shared.types import Workflow
    from verticals.banking.fraud_constraints import admit_claim_options

    world = _world()
    world.activate_scenario("synthetic-app-fraud-vulnerable" if vulnerable else "synthetic-app-fraud-claim")
    observation = world.current_fraud_observation()
    admitted = [{"option_id": r.option.option_id, "value_gbp": r.option.value_gbp}
                for r in admit_claim_options(observation) if r.feasible]
    context = {
        "workflow_id": workflow_id, "workflow_type": "app-fraud-reimbursement", "persona": "fraud_decision_manager",
        "phase": "Decide Reimbursement", "action": "banking.commit_reimbursement_decision",
        "request": {"amount_gbp": admitted[0]["value_gbp"], "category": "synthetic-app-fraud-reimbursement"},
        "observation": observation, "admitted_options": admitted, "selected_option": admitted[0],
        "selected_option_id": admitted[0]["option_id"], "ranking": {"reasoning": reasoning},
        "authority": {"allowed": True}, "decision_id": "SYN-APP-DECISION-001",
        "evidence_versions": observation["evidence_versions"],
    }
    now = time.time()
    app_state.store.upsert_workflow(Workflow(
        id=workflow_id, type="app-fraud-reimbursement", status="completed", current_phase="Decide Reimbursement",
        created_at=now, sla_due_at=now + 3600, jurisdiction="SYN-UK-Zava", agency="Zava Bank",
        payload={"hitl_context": context}))


def test_ask_the_persona_what_if_the_customer_were_vulnerable(monkeypatch) -> None:
    from api.server.routes import judgement as routes
    from api.server.services import persona_responder
    from api.server.services.judgement import engine
    from api.server.services.judgement.laya_client import LayaAnswer as A, LayaResult as R
    from api.server.state import app_state

    class Reads:
        enabled = True

        def available(self) -> bool:
            return True

        async def ask(self, state, questions):
            reads = {"says_vulnerable": 0.05, "says_no_marker": 0.95, "covers_no_action": 0.9}
            return R({q: A("noul", {"yes": reads[q], "no": 1 - reads[q]}, "yes" if reads[q] >= 0.5 else "no",
                           abs(2 * reads[q] - 1)) for q in questions}, 40.0, 41.0)

    monkeypatch.setenv("JUDGEMENT_ENABLED", "1")
    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "*")
    monkeypatch.setattr(engine, "get_client", lambda: Reads())
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()
    _judged_workflow(app_state, "BAPP-WHATIF-1", "No vulnerability flag is present. Doing nothing leaves the loss.", False)

    as_is = asyncio.run(routes.what_if(routes.WhatIf(workflow_id="BAPP-WHATIF-1")))
    assert as_is["ok"] and as_is["decision"] == "approve" and as_is["changed"] == []
    flipped = asyncio.run(routes.what_if(routes.WhatIf(workflow_id="BAPP-WHATIF-1", vulnerable=True)))
    assert flipped["changed"] == ["the vulnerability marker set"]
    assert "the record shows one" in " ".join(flipped["judgement"]["concerns"])
    assert flipped["decision"] in {"escalate", "approve"} and flipped["judgement"]["verdict"] in {"hold", "approve"}
    assert app_state.store.get_workflow("BAPP-WHATIF-1").payload["hitl_context"]["observation"]["claim"]["vulnerability_flag"] is False


def test_what_ifs_need_judgement_on(monkeypatch) -> None:
    from api.server.routes import judgement as routes

    monkeypatch.setenv("JUDGEMENT_ENABLED", "0")
    result = asyncio.run(routes.what_if(routes.WhatIf(workflow_id="x")))
    assert result["ok"] is False and "JUDGEMENT_ENABLED" in result["error"]


def test_status_reports_laya_and_the_budget(monkeypatch) -> None:
    from api.server.routes import judgement as routes

    status = asyncio.run(routes.judgement_status())
    assert set(status) == {"enabled", "laya", "deep_review"}
    assert {"budget_per_hour", "remaining", "model"} <= set(status["deep_review"])
