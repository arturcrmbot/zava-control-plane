"""The bank notices: payment references, the screener and world-noticed mule cases."""
from __future__ import annotations

import asyncio

import pytest

from api.server.services.judgement.laya_client import LayaAnswer, LayaResult, LayaUnavailable
from verticals.banking.fraud_constants import (
    FRAUD_BENEFICIARY_OVER_DELEGATION,
    FRAUD_BENEFICIARY_STANDARD,
    FRAUD_BENEFICIARY_VULNERABLE,
    FRAUD_SCENARIO_VULNERABLE,
)
from verticals.banking.worlds import reference_data
from verticals.banking.worlds.screening import (
    FLAG_PATTERNS,
    LayaScreener,
    RulesScreener,
    Screening,
    rules_screen,
)

# --- Reference data ---------------------------------------------------------------------


def test_mule_accounts_include_the_hero_beneficiaries() -> None:
    mules = reference_data.mule_beneficiary_ids()
    assert len(mules) == reference_data.MULE_ACCOUNT_COUNT == len(set(mules))
    assert {FRAUD_BENEFICIARY_STANDARD, FRAUD_BENEFICIARY_VULNERABLE, FRAUD_BENEFICIARY_OVER_DELEGATION} <= set(mules)
    assert reference_data.mule_beneficiary_ids() == mules  # seeded


def test_every_payment_has_a_reference_and_mule_payments_carry_scam_patterns() -> None:
    payments = reference_data.build_payments()
    mules = set(reference_data.mule_beneficiary_ids())
    references = reference_data.build_payment_references(payments, mules)
    assert set(references) == {p.id for p in payments}
    for payment in payments:
        pool = reference_data.SCAM_REFERENCES if payment.to_beneficiary_id in mules else reference_data.ORDINARY_REFERENCES
        assert references[payment.id] in pool


def test_references_do_not_disturb_the_seeded_book() -> None:
    before = [(p.id, p.amount_gbp, p.to_beneficiary_id) for p in reference_data.build_payments()]
    reference_data.build_payment_references(reference_data.build_payments(), set(reference_data.mule_beneficiary_ids()))
    after = [(p.id, p.amount_gbp, p.to_beneficiary_id) for p in reference_data.build_payments()]
    assert before == after
    bene = {b.id: b for b in reference_data.build_beneficiaries()}["SYN-BENE-141"]
    assert (bene.risk_band, bene.balance_gbp) == ("medium", 116_840.0)


# --- Screener -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("reference", "pattern"),
    [
        ("Safe account transfer as advised by bank", "safe_account"),
        ("HMRC penalty urgent payment", "authority_demand"),
        ("Release fee to unlock withdrawal", "unlock_fee"),
        ("Crypto wallet top up guaranteed returns", "high_returns"),
        ("Invoice 2291 kitchen units", "ordinary"),
    ],
)
def test_the_rules_screener_matches_keywords(reference: str, pattern: str) -> None:
    screening = rules_screen(reference)
    assert screening.pattern == pattern and screening.by == "rules"
    assert screening.flagged is (pattern in FLAG_PATTERNS)


def test_a_laya_screening_needs_a_clear_lead_to_flag() -> None:
    assert Screening("unlock_fee", 0.9, "laya").flagged is True
    assert Screening("unlock_fee", 0.2, "laya").flagged is False
    assert Screening("ordinary", 0.99, "laya").flagged is False


class _FakeClient:
    enabled = True

    def __init__(self, answers: dict[str, tuple[str, float]], *, fail: bool = False) -> None:
        self.answers, self.fail, self.calls = answers, fail, []

    def available(self) -> bool:
        return True

    async def ask(self, state, questions):
        self.calls.append(state["payment_reference"])
        if self.fail:
            raise LayaUnavailable("down")
        top, lead = self.answers[state["payment_reference"]]
        probs = {top: 0.5 + lead / 2, "unclear": 0.5 - lead / 2}
        return LayaResult({"pattern": LayaAnswer("choice", probs, top, lead)}, 40.0, 41.0)


def _screen_all(screener, references: list[str]) -> list[Screening]:
    results: list[Screening] = []

    async def run() -> None:
        for reference in references:
            screener.submit(reference, results.append)
        for _ in range(10):
            await asyncio.sleep(0)

    asyncio.run(run())
    return results


def test_the_laya_screener_reads_caches_and_falls_back() -> None:
    client = _FakeClient({"Fee to release parcel": ("unlock_fee", 1.0), "Book club": ("unclear", 0.82)})
    screener = LayaScreener(client_factory=lambda: client)
    first = _screen_all(screener, ["Fee to release parcel", "Book club", "Fee to release parcel"])
    # Two submissions of the same reference share one Laya call.
    assert sorted((s.pattern, s.by) for s in first) == [("unclear", "laya"), ("unlock_fee", "laya"), ("unlock_fee", "laya")]
    assert client.calls.count("Fee to release parcel") == 1
    failing = LayaScreener(client_factory=lambda: _FakeClient({}, fail=True))
    (fallback,) = _screen_all(failing, ["Safe account transfer as advised by bank"])
    assert (fallback.pattern, fallback.by) == ("safe_account", "rules")


def test_without_a_running_loop_the_laya_screener_uses_the_rules() -> None:
    results: list[Screening] = []
    LayaScreener(client_factory=lambda: _FakeClient({})).submit("Release fee to unlock withdrawal", results.append)
    assert [(s.pattern, s.by) for s in results] == [("unlock_fee", "rules")]


def test_the_rules_screener_answers_at_once() -> None:
    results: list[Screening] = []
    RulesScreener().submit("Bitcoin mining guaranteed profit", results.append)
    assert results[0].pattern == "high_returns"


# --- The world notices ---------------------------------------------------------------------

from api.server.world.model import SimulationCommand  # noqa: E402
from api.server.world.runtime import SimulationRuntime  # noqa: E402
from verticals.banking.support_constants import (  # noqa: E402
    MULE_COMMAND_TYPE,
    MULE_FUNCTION,
    MULE_SENSOR_ID,
    MULE_SUCCESS_EVENT,
)
from verticals.banking.worlds.scenario import ZavaBankWorld  # noqa: E402


@pytest.fixture
def screening_on(monkeypatch):
    monkeypatch.setenv("BANKING_WORLD_SCREENING", "1")


def _world(screener=None) -> ZavaBankWorld:
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42), screener=screener or RulesScreener())
    world.install()
    return world


def _run(world: ZavaBankWorld, minutes: float) -> None:
    world.runtime.env.run(until=world.runtime.env.now + minutes)


def _mule_trips(world: ZavaBankWorld) -> list:
    return [e for e in world.runtime.journal
            if e.type == "sensor.tripped" and e.payload.get("sensor_id") == MULE_SENSOR_ID]


def test_with_screening_off_the_world_is_as_before(monkeypatch) -> None:
    monkeypatch.delenv("BANKING_WORLD_SCREENING", raising=False)
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    _run(world, 600)
    assert not any(e.type == "banking.payment.flagged" for e in world.runtime.journal)
    assert _mule_trips(world) == []
    assert "screening" not in world.render_state()
    with pytest.raises(ValueError, match="BANKING_WORLD_SCREENING"):
        world.run_scenario("mule-activity")


def test_new_payments_are_screened_and_a_mule_pattern_opens_one_case(screening_on) -> None:
    world = _world()
    _run(world, 3_000)
    mules = set(reference_data.mule_beneficiary_ids())
    flagged = [e for e in world.runtime.journal if e.type == "banking.payment.flagged"]
    assert flagged and all(e.payload["screened_by"] == "rules" for e in flagged)
    assert all(e.payload["beneficiary_id"] in mules for e in flagged)
    assert all(e.payload["function"] == "financial-crime" for e in flagged)
    trips = _mule_trips(world)
    assert trips
    first = trips[0]
    bene = first.payload["beneficiary_id"]
    before = {e.payload["customer_id"] for e in flagged if e.payload["beneficiary_id"] == bene and e.seq < first.seq}
    assert len(before) >= 2
    assert len([t for t in trips if t.payload["beneficiary_id"] == bene]) == 1
    observation = world.build_observation(first.to_dict())
    case = observation["case"]
    account = world.beneficiaries[bene]
    assert (case["subject_id"], case["risk_band"], case["balance_gbp"]) == (bene, account.risk_band, account.balance_gbp)
    assert case["linked_claim_count"] >= 2 and len(case["flagged_payments"]) >= 2
    assert observation["trace_id"] == first.trace_id
    assert observation["evidence_versions"] == {case["id"]: account.version}
    state = world.render_state()["screening"]
    assert state["payments_flagged"] == len(flagged) and state["mule_cases_open"] >= 1


def test_mule_activity_on_demand_opens_a_case(screening_on) -> None:
    world = _world()
    event = world.run_scenario("mule-activity")["event"]
    assert event["type"] == "sensor.tripped" and event["payload"]["sensor_id"] == MULE_SENSOR_ID


def _command(world: ZavaBankWorld, trip: dict, option: str, number: int = 1, evidence: dict | None = None) -> SimulationCommand:
    bene = trip["payload"]["beneficiary_id"]
    if evidence is None:
        evidence = world.mule_observation(bene)["evidence_versions"] if bene in world._mule_cases else {}
    return SimulationCommand(
        command_id=f"SYN-MULE-CMD-{number}", trace_id=trip["trace_id"], issued_by=MULE_FUNCTION,
        type=MULE_COMMAND_TYPE,
        payload={"subject_id": bene, "option_id": option, "persona": "financial_crime_lead",
                 "decision_id": "d", "workflow_id": f"BMUL-{number}", "evidence_versions": evidence},
    )


def test_a_restraint_stops_the_account_receiving(screening_on) -> None:
    world = _world()
    trip = world.run_scenario("mule-activity")["event"]
    bene = trip["payload"]["beneficiary_id"]
    applied = world.apply_command(_command(world, trip, "SYN-MULE-OPTION-RESTRAIN"))
    assert applied.type == MULE_SUCCESS_EVENT and applied.payload["disposition"] == "restrained"
    assert applied.trace_id == trip["trace_id"]
    assert world.beneficiaries[bene].status == "restrained"
    mark = len(world.runtime.journal)
    _run(world, 6_000)
    later = [e for e in world.runtime.journal[mark:] if e.type == "banking.payment.settled" and e.target_id == bene]
    assert later == []
    assert world.apply_command(_command(world, trip, "SYN-MULE-OPTION-RESTRAIN", 2)).type == "command.rejected"


def test_monitoring_lets_the_pattern_continue_and_reopen(screening_on) -> None:
    world = _world()
    trip = world.run_scenario("mule-activity")["event"]
    bene = trip["payload"]["beneficiary_id"]
    assert world.apply_command(_command(world, trip, "SYN-MULE-OPTION-MONITOR")).type == MULE_SUCCESS_EVENT
    assert world.beneficiaries[bene].status == "monitored"
    again = world.run_scenario(f"mule-activity:{bene}")["event"]
    assert again["type"] == "sensor.tripped" and again["payload"]["beneficiary_id"] == bene
    assert again["payload"]["round"] == 2
    assert len([t for t in _mule_trips(world) if t.payload["beneficiary_id"] == bene]) == 2


def test_a_disposition_decided_on_moved_evidence_is_rejected(screening_on) -> None:
    world = _world()
    trip = world.run_scenario("mule-activity")["event"]
    bene = trip["payload"]["beneficiary_id"]
    stale = world.mule_observation(bene)["evidence_versions"]
    world.beneficiaries[bene].version += 1  # something changed the account after the gate's snapshot
    rejected = world.apply_command(_command(world, trip, "SYN-MULE-OPTION-MONITOR", evidence=stale))
    assert rejected.type == "command.rejected"
    assert rejected.payload["reason"] == "world evidence moved after the approval checkpoint"
    assert world.beneficiaries[bene].status == "under_review"


def test_a_restraint_holds_everything_including_funds_already_frozen(screening_on) -> None:
    world = _world()
    trip = world.run_scenario("mule-activity")["event"]
    account = world.beneficiaries[trip["payload"]["beneficiary_id"]]
    account.frozen_gbp, account.balance_gbp = 1_000.0, 5_000.0
    trip_evidence = world.mule_observation(account.id)["evidence_versions"]
    applied = world.apply_command(_command(world, trip, "SYN-MULE-OPTION-RESTRAIN", evidence=trip_evidence))
    assert applied.type == MULE_SUCCESS_EVENT
    assert (account.frozen_gbp, account.balance_gbp) == (6_000.0, 0.0)


def _fail_objective(world: ZavaBankWorld, sensor: dict, reason: str) -> None:
    """Journal a failed objective for this sensor, as the world bridge and gateway do."""
    from api.server.world.objectives import ObjectiveManager
    from api.server.world.registry import ObjectiveRoute

    route = ObjectiveRoute(sensor_id=MULE_SENSOR_ID, objective_type="mule_case", allowed_command_types=frozenset(),
                           success_event_types=frozenset(), failure_event_types=frozenset(),
                           evaluation_timeout_minutes=5)
    manager = ObjectiveManager(world.runtime)
    objective = manager.open(sensor, route, owner_function=MULE_FUNCTION)
    manager.transition(objective.id, "failed", payload={"reason": reason})


def test_a_case_that_ends_without_a_disposition_closes_and_the_pattern_can_reopen_it(screening_on) -> None:
    world = _world()
    trip = world.run_scenario("mule-activity")["event"]
    bene = trip["payload"]["beneficiary_id"]
    assert world.beneficiaries[bene].status == "under_review"
    world.bind_story_workflow(trip, "BMUL-1")
    _fail_objective(world, trip, "financial_crime_lead declined to approve")
    world.fail_story_workflow("BMUL-1", "financial_crime_lead declined to approve")
    assert world._mule_cases[bene]["status"] == "unresolved"
    assert world.beneficiaries[bene].status == "open"
    unresolved = [e for e in world.runtime.journal if e.type == "banking.mule_case.unresolved"]
    assert unresolved and unresolved[-1].payload["reason"] == "financial_crime_lead declined to approve"
    assert unresolved[-1].trace_id == trip["trace_id"]
    assert world.render_state()["screening"]["mule_cases_open"] == 0
    again = world.run_scenario(f"mule-activity:{bene}")["event"]
    assert again["type"] == "sensor.tripped" and again["payload"]["round"] == 2


def test_a_case_whose_orchestration_never_started_closes_too(screening_on) -> None:
    # Scheduling failed: the bridge fails the objective before any workflow exists.
    world = _world()
    trip = world.run_scenario("mule-activity")["event"]
    bene = trip["payload"]["beneficiary_id"]
    _fail_objective(world, trip, "the Functions host did not answer")
    _run(world, 60)
    assert world._mule_cases[bene]["status"] == "unresolved"
    unresolved = [e for e in world.runtime.journal if e.type == "banking.mule_case.unresolved"]
    assert unresolved[-1].payload["reason"] == "the Functions host did not answer"


def test_the_story_hooks_leave_fraud_claims_alone(screening_on) -> None:
    world = _world()
    sensor = world.raise_claim("any")
    claim_id = sensor.payload["claim_id"]
    mark = len(world.runtime.journal)
    world.bind_story_workflow(sensor.to_dict(), "BAPP-1")
    world.fail_story_workflow("BAPP-1", "timed out")
    assert world.fraud_claims[claim_id].status == "reported"
    assert len(world.runtime.journal) == mark


def test_no_mule_case_opens_on_an_account_a_claim_is_being_decided_on(screening_on) -> None:
    # A case there would move the account under the claim's approval; the
    # flags wait, and the bank looks once the claim is decided.
    world = _world()
    sensor = world.activate_scenario(FRAUD_SCENARIO_VULNERABLE)
    claim_id = sensor.payload["claim_id"]
    bene = world.fraud_claims[claim_id].beneficiary_id
    assert bene in reference_data.mule_beneficiary_ids()
    before = world.observation_for_claim(claim_id)["evidence_versions"]
    approval = world.command_for_claim_option(
        claim_id=claim_id, option_id=OPTION_REIMBURSE_FULL, workflow_id="BAPP-V1",
        decision_id="SYN-APP-DECISION-001", persona=FRAUD_HITL_PERSONA)
    flagged = world.run_scenario(f"mule-activity:{bene}")["event"]
    assert flagged["type"] == "banking.payment.flagged" and bene not in world._mule_cases
    assert world.observation_for_claim(claim_id)["evidence_versions"] == before
    assert world.apply_command(approval).type == "banking.reimbursement.applied"


def test_story_accounts_wait_for_their_story_before_a_mule_case(screening_on) -> None:
    world = _world()
    heroes = {FRAUD_BENEFICIARY_STANDARD, FRAUD_BENEFICIARY_VULNERABLE, FRAUD_BENEFICIARY_OVER_DELEGATION}
    flagged = world.run_scenario(f"mule-activity:{FRAUD_BENEFICIARY_VULNERABLE}")["event"]
    assert flagged["type"] == "banking.payment.flagged" and FRAUD_BENEFICIARY_VULNERABLE not in world._mule_cases
    for _ in range(3):
        trip = world.run_scenario("mule-activity")["event"]
        assert trip["type"] == "sensor.tripped" and trip["payload"]["beneficiary_id"] not in heroes
    _run(world, 6_000)
    assert not heroes & {t.payload["beneficiary_id"] for t in _mule_trips(world)}


def test_a_story_keeps_a_restrained_account_restrained(screening_on) -> None:
    world = _world()
    world.beneficiaries[FRAUD_BENEFICIARY_VULNERABLE].status = "restrained"
    world.activate_scenario(FRAUD_SCENARIO_VULNERABLE)
    assert world.beneficiaries[FRAUD_BENEFICIARY_VULNERABLE].status == "restrained"
    assert FRAUD_BENEFICIARY_VULNERABLE not in world._active_mules()


def test_a_call_about_a_restrained_mule_keeps_it_restrained(screening_on) -> None:
    world = _world()
    trip = world.run_scenario("mule-activity")["event"]
    bene = trip["payload"]["beneficiary_id"]
    assert world.apply_command(_command(world, trip, "SYN-MULE-OPTION-RESTRAIN")).type == MULE_SUCCESS_EVENT
    payment_id = next(p.id for p in world.payments.values() if p.to_beneficiary_id == bene and p.status == "settled"
                      and world.customers[world.accounts[p.from_account_id].customer_id].status == "active")
    world.customer_calls(payment_id, "A man from the bank's fraud team told me to move my savings.", None)
    assert world.beneficiaries[bene].status == "restrained"
    assert bene not in world._active_mules()


def test_a_call_is_refused_while_the_receiving_account_is_under_a_mule_investigation(screening_on) -> None:
    world = _world()
    trip = world.run_scenario("mule-activity")["event"]
    bene = trip["payload"]["beneficiary_id"]
    evidence = world.mule_observation(bene)["evidence_versions"]
    payment_id = next(p.id for p in world.payments.values() if p.to_beneficiary_id == bene and p.status == "settled")
    with pytest.raises(ValueError, match="mule investigation"):
        world.customer_calls(payment_id, "A man from the bank's fraud team told me to move my savings.", None)
    assert world.mule_observation(bene)["evidence_versions"] == evidence


# --- The world owns mule cases when screening is on ----------------------------------------

import importlib  # noqa: E402

from verticals.banking import supporting_durable  # noqa: E402
from verticals.banking.support_constants import MULE_OBJECTIVE_TYPE, MULE_ORCHESTRATOR  # noqa: E402


def _reload_registry():
    from verticals.banking import domains
    from verticals.banking.worlds import registration

    return importlib.reload(domains), importlib.reload(registration)


@pytest.fixture
def registry(monkeypatch):
    yield
    monkeypatch.delenv("BANKING_WORLD_SCREENING", raising=False)
    _reload_registry()


def test_with_screening_on_the_world_owns_mule_cases(registry, monkeypatch) -> None:
    monkeypatch.setenv("BANKING_WORLD_SCREENING", "1")
    domains, registration = _reload_registry()
    mule = domains.BANKING_DOMAINS["mule-account-investigation"]
    assert mule.spawn_fn is None and mule.realistic_interval_seconds is None
    routes = {route.sensor_id: route for route in registration.BANKING_WORLD.objective_routes}
    assert routes[MULE_SENSOR_ID].objective_type == MULE_OBJECTIVE_TYPE
    assert routes[MULE_SENSOR_ID].allowed_command_types == frozenset({MULE_COMMAND_TYPE})
    assert routes[MULE_SENSOR_ID].success_event_types == frozenset({MULE_SUCCESS_EVENT})
    responder = registration.BANKING_WORLD.responders[MULE_OBJECTIVE_TYPE]
    assert (responder.orchestrator, responder.owner_function) == (MULE_ORCHESTRATOR, MULE_FUNCTION)
    merchant = domains.BANKING_DOMAINS["merchant-onboarding-risk"]
    assert merchant.spawn_fn is not None


def test_with_screening_off_mule_cases_are_spawned_as_before(registry, monkeypatch) -> None:
    monkeypatch.delenv("BANKING_WORLD_SCREENING", raising=False)
    domains, registration = _reload_registry()
    assert domains.BANKING_DOMAINS["mule-account-investigation"].spawn_fn is not None
    assert MULE_SENSOR_ID not in {route.sensor_id for route in registration.BANKING_WORLD.objective_routes}
    assert MULE_OBJECTIVE_TYPE not in registration.BANKING_WORLD.responders


def _world_case_input(screening_world: ZavaBankWorld) -> tuple[dict, dict]:
    trip = screening_world.run_scenario("mule-activity")["event"]
    observation = screening_world.build_observation(trip)
    return trip, {"workflow_id": "BMUL-W1", "type": "mule-account-investigation",
                  "trace_id": trip["trace_id"], "objective_id": "obj-1", "observation": observation}


def test_a_world_case_is_assessed_from_the_worlds_observation(screening_on) -> None:
    trip, payload = _world_case_input(_world())
    evidence = supporting_durable.case_evidence_activity(payload)
    case = payload["observation"]["case"]
    assert evidence["case_id"] == case["id"] and evidence["story_id"] == payload["observation"]["story_id"]
    assert evidence["observation"]["trace_id"] == trip["trace_id"]
    assert evidence["evidence_versions"] == payload["observation"]["evidence_versions"]
    assert {o["option_id"] for o in evidence["admitted_options"]}


def _approval(evidence: dict, option_id: str) -> dict:
    return {"decision": "approve", "persona": "financial_crime_lead", "decision_id": "SYN-MULE-DECISION-1",
            "selected_option_id": option_id, "evidence_versions": evidence["evidence_versions"]}


def test_a_world_case_command_is_a_full_world_command(screening_on) -> None:
    world = _world()
    trip, payload = _world_case_input(world)
    evidence = supporting_durable.case_evidence_activity(payload)
    option = evidence["admitted_options"][0]
    result = supporting_durable.case_command_activity({
        "workflow_id": "BMUL-W1", "workflow_type": "mule-account-investigation",
        "approval": _approval(evidence, option["option_id"]),
        "hitl_context": {"admitted_options": evidence["admitted_options"], "observation": evidence["observation"],
                         "evidence_versions": evidence["evidence_versions"], "case_id": evidence["case_id"],
                         "selected_option": option},
    })
    command = result["command"]
    assert set(command) == {"command_id", "trace_id", "issued_by", "type", "payload"}
    assert (command["trace_id"], command["issued_by"]) == (trip["trace_id"], MULE_FUNCTION)
    assert command["payload"]["subject_id"] == trip["payload"]["beneficiary_id"]
    applied = world.apply_command(SimulationCommand(**command))
    assert applied.type == MULE_SUCCESS_EVENT


def test_a_spawned_case_command_is_unchanged() -> None:
    evidence = supporting_durable.case_evidence_activity({
        "workflow_id": "BMUL-S1", "type": "mule-account-investigation",
        "case": {"id": "SYN-MULE-CASE-0001", "subject_id": "SYN-BENE-010", "risk_band": "medium", "version": 1},
    })
    option = evidence["admitted_options"][0]
    result = supporting_durable.case_command_activity({
        "workflow_id": "BMUL-S1", "workflow_type": "mule-account-investigation",
        "approval": _approval(evidence, option["option_id"]),
        "hitl_context": {"admitted_options": evidence["admitted_options"], "observation": evidence["observation"],
                         "evidence_versions": evidence["evidence_versions"], "case_id": evidence["case_id"],
                         "selected_option": option},
    })
    assert set(result["command"]) == {"command_id", "type", "payload"}
    assert "subject_id" not in result["command"]["payload"]
    assert result["evaluation"]["world_mutation"] == "not_applicable"


# --- Customers react to decisions ------------------------------------------------------------

import random as _random  # noqa: E402

from verticals.banking.fraud_constants import FRAUD_HITL_PERSONA, FRAUD_SCENARIO_STANDARD  # noqa: E402
from verticals.banking.fraud_constraints import OPTION_REIMBURSE_CAPPED, OPTION_REIMBURSE_FULL, OPTION_REFUSE_CAUTION  # noqa: E402
from verticals.banking.worlds.reactions import (  # noqa: E402
    LayaReactor,
    Mood,
    RulesReactor,
    draw,
    reaction_odds,
)


def test_rules_reactions_follow_the_outcome() -> None:
    moods: list[Mood] = []
    reactor = RulesReactor()
    for kind in ("full", "capped", "refused"):
        reactor.submit("A personal customer", "decision", kind, moods.append)
    assert [max(reaction_odds(m), key=reaction_odds(m).get) for m in moods] == ["accepts", "chases", "complains"]
    assert all(m.by == "rules" for m in moods)


def test_the_upset_scale_becomes_reaction_odds_and_a_seeded_draw() -> None:
    calm = reaction_odds(Mood((0.9, 0.1, 0.0, 0.0), 0.1, "laya"))
    angry = reaction_odds(Mood((0.0, 0.0, 0.3, 0.7), 2.7, "laya"))
    assert calm["accepts"] > 0.9 and angry["complains"] > 0.6
    assert abs(sum(angry.values()) - 1.0) < 1e-9
    rng = _random.Random(7)
    assert draw(calm, _random.Random(7)) == draw(calm, rng)  # seeded


class _UpsetClient:
    enabled = True

    def __init__(self) -> None:
        self.calls = 0

    def available(self) -> bool:
        return True

    async def ask(self, state, questions):
        self.calls += 1
        levels = {"0": 0.05, "1": 0.15, "2": 0.4, "3": 0.4} if "refused" in state["decision"] else {"0": 0.8, "1": 0.2, "2": 0.0, "3": 0.0}
        score = sum(int(k) * v for k, v in levels.items())
        return LayaResult({"upset": LayaAnswer("score", levels, max(levels, key=levels.get), 0.0, score)}, 30.0, 31.0)


def test_the_laya_reactor_reads_the_mood_once_per_situation() -> None:
    client = _UpsetClient()
    reactor = LayaReactor(client_factory=lambda: client)
    moods: list[Mood] = []

    async def run() -> None:
        for _ in range(3):
            reactor.submit("A personal customer who lost GBP 900", "The bank refused the claim.", "refused", moods.append)
        for _ in range(10):
            await asyncio.sleep(0)
        reactor.submit("A personal customer who lost GBP 900", "The bank refused the claim.", "refused", moods.append)

    asyncio.run(run())
    assert len(moods) == 4 and client.calls == 1
    assert all(m.by == "laya" and m.score > 2 for m in moods)


def test_a_reimbursed_customer_reacts_in_the_world(screening_on) -> None:
    world = _world()
    world.activate_scenario(FRAUD_SCENARIO_STANDARD)
    observation = world.current_fraud_observation()
    command = world.command_for_claim_option(
        claim_id=observation["claim"]["id"], option_id=OPTION_REIMBURSE_FULL, workflow_id="BAPP-R1",
        decision_id="SYN-APP-DECISION-001", persona=FRAUD_HITL_PERSONA)
    applied = world.apply_command(command)
    assert applied.type == "banking.reimbursement.applied"
    reacted = [e for e in world.runtime.journal if e.type == "banking.customer.reacted"]
    assert len(reacted) == 1
    event = reacted[0]
    assert event.trace_id == applied.trace_id and event.payload["reaction"] == "accepts"
    assert event.payload["reacted_by"] == "rules" and event.payload["customer_id"] == observation["customer"]["id"]
    assert event.payload["function"] == "retail-banking"
    assert world.render_state()["screening"]["customer_reactions"] == {"accepts": 1, "chases": 0, "complains": 0}


def test_without_screening_customers_do_not_react(monkeypatch) -> None:
    monkeypatch.delenv("BANKING_WORLD_SCREENING", raising=False)
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    world.activate_scenario(FRAUD_SCENARIO_STANDARD)
    observation = world.current_fraud_observation()
    world.apply_command(world.command_for_claim_option(
        claim_id=observation["claim"]["id"], option_id=OPTION_REIMBURSE_FULL, workflow_id="BAPP-R2",
        decision_id="SYN-APP-DECISION-001", persona=FRAUD_HITL_PERSONA))
    assert not any(e.type == "banking.customer.reacted" for e in world.runtime.journal)


def test_reactions_cover_every_decision_word() -> None:
    from verticals.banking.worlds.reactions import decision_kind

    assert decision_kind(OPTION_REIMBURSE_FULL) == "full"
    assert decision_kind(OPTION_REIMBURSE_CAPPED) == "capped"
    assert decision_kind(OPTION_REFUSE_CAUTION) == "refused"
