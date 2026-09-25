"""The bank notices: payment references, the screener and world-noticed mule cases."""
from __future__ import annotations

import asyncio

import pytest

from api.server.services.judgement.laya_client import LayaAnswer, LayaResult, LayaUnavailable
from verticals.banking.fraud_constants import (
    FRAUD_BENEFICIARY_OVER_DELEGATION,
    FRAUD_BENEFICIARY_STANDARD,
    FRAUD_BENEFICIARY_VULNERABLE,
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


def _command(world: ZavaBankWorld, trip: dict, option: str, number: int = 1) -> SimulationCommand:
    return SimulationCommand(
        command_id=f"SYN-MULE-CMD-{number}", trace_id=trip["trace_id"], issued_by=MULE_FUNCTION,
        type=MULE_COMMAND_TYPE,
        payload={"subject_id": trip["payload"]["beneficiary_id"], "option_id": option, "persona": "financial_crime_lead",
                 "decision_id": "d", "workflow_id": f"BMUL-{number}"},
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
