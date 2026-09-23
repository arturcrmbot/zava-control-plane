"""Banking vertical: outcomes, governance, world contract, projections, relay.

These pin the behaviour the demo depends on, so a regression shows up here
rather than on stage.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from api.server.services.governance.kernel import GovernanceKernel
from api.server.world.runtime import SimulationRuntime
from api.shared.events import FleetEvent
from api.shared.vertical_loader import active_runtime, build_runtime
from verticals.banking.detail import workflow_detail
from verticals.banking.entity_projections import fraud as fraud_projection
from verticals.banking.entity_projections import supporting as supporting_projection
from verticals.banking.fraud_constants import (
    FRAUD_COMMAND_TYPE,
    FRAUD_HITL_CATEGORY,
    FRAUD_HITL_PERSONA,
    FRAUD_SCENARIO_OVER_DELEGATION,
    FRAUD_SCENARIO_STANDARD,
    FRAUD_SCENARIO_VULNERABLE,
)
from verticals.banking.fraud_constraints import (
    OPTION_REFUSE_CAUTION,
    OPTION_REIMBURSE_CAPPED,
    OPTION_REIMBURSE_FULL,
    admit_claim_options,
)
from verticals.banking.worlds.scenario import ZavaBankWorld


def _world(scenario: str | None = None) -> ZavaBankWorld:
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    if scenario is not None:
        world.activate_scenario(scenario)
    return world


def _admission(scenario: str) -> tuple[set[str], dict[str, tuple[str, ...]]]:
    results = admit_claim_options(_world(scenario).current_fraud_observation())
    feasible = {r.option.option_id for r in results if r.feasible}
    rejected = {r.option.option_id: r.reasons for r in results if not r.feasible}
    return feasible, rejected


# --- Pack --------------------------------------------------------------------


def test_banking_pack_is_discovered_and_valid(tmp_path) -> None:
    runtime = build_runtime({"ZAVA_VERTICAL": "banking"}, data_root=tmp_path)
    live = [d for d in runtime.pack.domains.values() if not d.stub]
    assert runtime.pack.name == "banking"
    assert {d.workflow_type for d in live} == {
        "app-fraud-reimbursement",
        "mule-account-investigation",
        "merchant-onboarding-risk",
    }
    # Every live process does real agent work.
    assert all(any(p.kind == "agent" for p in d.phases) for d in live)
    # The hero is world-owned, so only the supporting processes ramp.
    assert set(runtime.pack.ramp_workflow_types) == {
        "mule-account-investigation",
        "merchant-onboarding-risk",
    }


# --- Three outcomes from evidence ----------------------------------------------


def test_standard_claim_admits_full_reimbursement_only() -> None:
    feasible, _ = _admission(FRAUD_SCENARIO_STANDARD)
    assert OPTION_REIMBURSE_FULL in feasible
    assert OPTION_REFUSE_CAUTION not in feasible


def test_vulnerable_customer_can_never_be_refused() -> None:
    feasible, rejected = _admission(FRAUD_SCENARIO_VULNERABLE)
    assert OPTION_REFUSE_CAUTION not in feasible
    assert any("vulnerab" in reason for reason in rejected[OPTION_REFUSE_CAUTION])


def test_over_cap_claim_is_capped_not_reimbursed_in_full() -> None:
    feasible, _ = _admission(FRAUD_SCENARIO_OVER_DELEGATION)
    assert OPTION_REIMBURSE_CAPPED in feasible
    assert OPTION_REIMBURSE_FULL not in feasible


# --- Real governance ------------------------------------------------------------


@pytest.fixture
def banking_kernel(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ZAVA_VERTICAL", "banking")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    try:
        yield GovernanceKernel()
    finally:
        active_runtime.cache_clear()


def test_claims_manager_may_approve_within_delegation(banking_kernel) -> None:
    authority = banking_kernel.check_authority(
        role=FRAUD_HITL_PERSONA,
        action=FRAUD_COMMAND_TYPE,
        category=FRAUD_HITL_CATEGORY,
        value=18_400.0,
    )
    assert authority.allowed is True


def test_capped_claim_is_refused_and_names_who_can_authorise(banking_kernel) -> None:
    authority = banking_kernel.check_authority(
        role=FRAUD_HITL_PERSONA,
        action=FRAUD_COMMAND_TYPE,
        category=FRAUD_HITL_CATEGORY,
        value=85_000.0,
    )
    assert authority.allowed is False
    assert authority.governing_rule_id == (
        "AUTH-financial_crime_lead-banking.commit_reimbursement_decision"
    )


# --- World contract ---------------------------------------------------------------


def test_every_world_event_declares_its_owning_function() -> None:
    world = _world()
    start = len(world.runtime.journal)
    world.runtime.run_until(60.0)
    world.activate_scenario(FRAUD_SCENARIO_STANDARD)
    events = world.runtime.journal[start:]
    assert events, "the world must keep working with no workflow running"
    untagged = sorted({e.type for e in events if not (e.payload or {}).get("function")})
    assert untagged == []
    functions = {e.payload["function"] for e in events}
    assert {"payments", "credit-risk", "markets", "retail-banking"} <= functions


def test_snapshot_is_bounded_and_carries_counts_for_the_large_book() -> None:
    world = _world()
    world.runtime.run_until(60.0)
    snapshot = world.render_state()
    assert len(json.dumps(snapshot)) < 100_000
    for large in ("customers", "accounts", "payments"):
        assert large not in snapshot
    bank = snapshot["bank"]
    assert bank["customer_count"] > 1_000
    assert bank["payments_settled_total"] > 0
    assert len(snapshot["recent_settlements"]) <= 24


def test_a_hero_claim_is_raised_only_once_its_story_starts() -> None:
    world = _world()
    assert not any(c["raised"] for c in world.render_state()["fraud_claims"])
    world.activate_scenario(FRAUD_SCENARIO_STANDARD)
    raised = {c["id"] for c in world.render_state()["fraud_claims"] if c["raised"]}
    assert raised == {"SYN-CLAIM-0031"}


# --- Orchestration: resilient agent work, refusals the world can explain ------------


class _RecordingContext:
    """Just enough of DurableOrchestrationContext to step the generator."""

    instance_id = "inst-test"

    def __init__(self, input_: dict) -> None:
        self._input = input_
        self.calls: list[tuple[str, object]] = []

    def get_input(self) -> dict:
        return self._input

    def call_activity(self, name: str, payload: dict) -> str:
        self.calls.append((name, None))
        return name

    def call_activity_with_retry(self, name: str, retry, payload: dict) -> str:
        self.calls.append((name, retry))
        return name


def _run_to_refusal() -> tuple[dict, _RecordingContext]:
    from verticals.banking.fraud_durable import fraud_orchestration

    context = _RecordingContext({"workflow_id": "BAPP-test-refusal"})
    results = {
        "fraud_evidence_activity_trigger": {},
        "fraud_trace_activity_trigger": {
            "admitted_options": [{"option_id": OPTION_REIMBURSE_CAPPED, "value_gbp": 85_000.0}]
        },
        "fraud_agent_activity_trigger": {"ranked_option_ids": [OPTION_REIMBURSE_CAPPED]},
        "fraud_governance_activity_trigger": {
            "allowed": False,
            "reason": "value exceeds delegated authority",
            "governing_rule_id": "AUTH-financial_crime_lead-banking.commit_reimbursement_decision",
        },
    }
    orchestration = fraud_orchestration(context)
    sent = None
    try:
        while True:
            sent = results.get(orchestration.send(sent))
    except StopIteration as stop:
        return stop.value, context


def test_a_refusal_reaches_the_world_bridge_with_its_reason() -> None:
    output, _ = _run_to_refusal()
    # command=None plus `reasoning` is the bridge's deferral contract, so the
    # world records responder.deferred with this text instead of a failure.
    assert output["command"] is None
    assert "AUTH-financial_crime_lead" in output["reasoning"]


def test_agent_work_is_retried_but_governance_is_not() -> None:
    import azure.durable_functions as df

    _, context = _run_to_refusal()
    retried = {name for name, retry in context.calls if isinstance(retry, df.RetryOptions)}
    assert retried == {"fraud_agent_activity_trigger"}


# --- Projections read the shape the store persists ----------------------------------


def _hero_observation(scenario: str = FRAUD_SCENARIO_STANDARD) -> dict:
    return _world(scenario).current_fraud_observation()


def test_completed_hero_projects_the_human_decision() -> None:
    workflow = SimpleNamespace(
        id="BAPP-test-1",
        status="completed",
        payload={
            "observation": _hero_observation(),
            "evidence": {
                "approval": {
                    "decision": "approve",
                    "persona": FRAUD_HITL_PERSONA,
                    "selected_option_id": OPTION_REIMBURSE_FULL,
                },
                "hitl_context": {
                    "selected_option": {
                        "option_id": OPTION_REIMBURSE_FULL,
                        "value_gbp": 18_400.0,
                    },
                    "authority": {"governing_rule_id": "AUTH-rule"},
                },
            },
        },
    )
    records = list(fraud_projection.project(workflow))
    decisions = [r for r in records if isinstance(r, DecisionWrite)]
    assert any(isinstance(r, RelWrite) and r.rel == "TRANSACTS" for r in records)
    assert len(decisions) == 1
    assert decisions[0].persona_role == FRAUD_HITL_PERSONA
    assert decisions[0].attributes["decided_via"] == "operator"


def test_a_mule_account_serving_a_corporate_client_is_linked_to_it() -> None:
    owns = set()
    for scenario in (
        FRAUD_SCENARIO_STANDARD,
        FRAUD_SCENARIO_VULNERABLE,
        FRAUD_SCENARIO_OVER_DELEGATION,
    ):
        workflow = SimpleNamespace(
            id=f"BAPP-{scenario}",
            status="failed",
            payload={"observation": _hero_observation(scenario)},
        )
        owns |= {
            (r.src_id, r.dst_id)
            for r in fraud_projection.project(workflow)
            if isinstance(r, RelWrite) and r.rel == "OWNS"
        }
    assert any(dst == "SYN-CORP-014" for _, dst in owns)


def test_refused_hero_projects_entities_but_invents_no_decision() -> None:
    workflow = SimpleNamespace(
        id="BAPP-test-2",
        status="failed",
        payload={"observation": _hero_observation()},
    )
    records = list(fraud_projection.project(workflow))
    assert any(isinstance(r, EntityWrite) for r in records)
    assert not any(isinstance(r, DecisionWrite) for r in records)


def test_supporting_decisions_come_from_the_persisted_decision_list() -> None:
    workflow = SimpleNamespace(
        id="BMUL-test",
        status="completed",
        payload={
            "case": {
                "id": "SYN-MULE-CASE-9",
                "subject_id": "SYN-BENE-171",
                "subject_kind": "beneficiary",
                "risk_band": "high",
            },
            "decisions": [
                {
                    "phase": "Approve Account Disposition",
                    "persona_role": "financial_crime_lead",
                    "verdict": "approve",
                    "reason": "within delegation",
                    "decided_at": "2026-09-23T08:22:07+00:00",
                    "source_event": "financial_crime_lead_decision",
                }
            ],
        },
    )
    decisions = [
        r for r in supporting_projection.project(workflow) if isinstance(r, DecisionWrite)
    ]
    assert [d.persona_role for d in decisions] == ["financial_crime_lead"]
    assert decisions[0].decided_at == "2026-09-23T08:22:07+00:00"


# --- A refused workflow explains itself -----------------------------------------------


def test_governance_refusal_is_explained_not_shown_as_a_crash() -> None:
    workflow = SimpleNamespace(
        id="BAPP-test-3",
        type="app-fraud-reimbursement",
        payload={"observation": _hero_observation()},
        metadata={
            "rejected": True,
            "rejected_at_phase": "Decide Reimbursement",
            "rejected_by": "orchestrator",
            "rejection_reason": "not authorised (matched rule AUTH-financial_crime_lead-x)",
        },
    )
    refusal = workflow_detail(workflow)["governanceRefusal"]
    assert refusal["refusedAtPhase"] == "Decide Reimbursement"
    assert "AUTH-financial_crime_lead" in refusal["reason"]


# --- Relay: the world reaches the observatory without crowding it ----------------------


def _world_event(world_type: str, function: str | None) -> FleetEvent:
    payload = {"location_id": "SYN-RAIL-FLOOR"}
    if function is not None:
        payload["function"] = function
    return FleetEvent(
        type=f"world.{world_type}",
        trace_id="trace-1",
        simulation_event={
            "type": world_type,
            "actor_id": "SYN-PAY-00001",
            "target_id": "SYN-RAIL-FPS",
            "payload": payload,
        },
    )


def test_function_tagged_world_events_become_ambient_activity() -> None:
    from api.server.routes.blueprint import _normalise_event

    flash = _normalise_event(_world_event("banking.payment.settled", "payments"))
    assert flash is not None
    assert flash["type"] == "world.activity"
    assert flash["function"] == "payments"
    assert flash["world_type"] == "banking.payment.settled"


def test_untagged_world_events_stay_out_of_the_stream() -> None:
    from api.server.routes.blueprint import _normalise_event

    assert _normalise_event(_world_event("banking.payment.settled", None)) is None


def test_routine_world_activity_is_coalesced_per_function() -> None:
    from api.server.routes.blueprint import _normalise_event, _WorldActivityCoalescer

    coalescer = _WorldActivityCoalescer(window_s=60.0)
    admitted = [
        flash
        for flash in (
            coalescer.admit(_normalise_event(_world_event("banking.payment.settled", "payments")))
            for _ in range(5)
        )
        if flash is not None
    ]
    assert len(admitted) == 1
    # One function's window never holds back another function.
    other = coalescer.admit(
        _normalise_event(_world_event("banking.exposure.revalued", "credit-risk"))
    )
    assert other is not None


def test_a_sensor_trip_is_never_coalesced() -> None:
    from api.server.routes.blueprint import _normalise_event, _WorldActivityCoalescer

    coalescer = _WorldActivityCoalescer(window_s=60.0)
    first = coalescer.admit(_normalise_event(_world_event("sensor.tripped", "retail-banking")))
    second = coalescer.admit(_normalise_event(_world_event("sensor.tripped", "retail-banking")))
    assert first is not None and second is not None


# --- Knowledge view shows this pack's vocabulary, not another's ----------------------------


def test_the_cast_is_the_banks_own_decision_makers(monkeypatch) -> None:
    import asyncio

    from api.server.data_fabric.narrative_arcs import ARCS
    from api.server.routes.personas import narrative_arcs

    monkeypatch.setenv("ZAVA_VERTICAL", "banking")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    try:
        cast = asyncio.run(narrative_arcs())
    finally:
        active_runtime.cache_clear()
    by_role = {person["role"]: person for person in cast}
    assert FRAUD_HITL_PERSONA in by_role
    assert by_role[FRAUD_HITL_PERSONA]["name"] == "Fraud decision manager"
    assert by_role[FRAUD_HITL_PERSONA]["function"] == "retail-banking"
    assert all(0 < len(person["one_liner"]) <= 120 for person in cast)
    assert not {arc.name for arc in ARCS} & {person["name"] for person in cast}


def test_entity_cities_hide_absent_pack_kinds_and_show_present_ones(monkeypatch) -> None:
    from api.server.routes import cities
    from api.server.state import app_state

    counts = {kind: 0 for kind in cities.CORE_ENTITY_KINDS}
    counts.update({"Account": 12, "Brand": 0, "Campaign": 0})
    stub = SimpleNamespace(
        count_by_kind=lambda: counts,
        recent_activity_per_min=lambda kind: 0.0,
    )
    monkeypatch.setattr(app_state, "entities", stub, raising=False)
    labels = {city["label"] for city in cities._gather_entity_types()}
    assert "Account" in labels
    assert "Person" in labels
    assert not {"Brand", "Campaign"} & labels
