"""Causal-signal, cohort/lifecycle, and real-entity behaviours for the Fashion
actor world (Task 3 remediation). Every test here mutates or removes a causal
input and asserts a changed signal, evidence field, or decision branch — field
presence alone is not sufficient."""
from copy import deepcopy

import pytest

from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.world import FashionScenario


def _scenario(seed: int = 42) -> FashionScenario:
    scenario = FashionScenario.demo(SimulationRuntime(seed))
    scenario.install()
    return scenario


def _case_command(
    scenario: FashionScenario,
    workflow_type: str,
    *,
    command_id: str | None = None,
) -> tuple[object, SimulationCommand]:
    profile = FASHION_PROCESS_PROFILES[workflow_type]
    result = scenario.run_case(workflow_type)
    case = scenario.process_cases[result["case_id"]]
    payload = scenario.command_payload(case.id)
    return case, SimulationCommand(
        command_id=command_id or f"cmd-{workflow_type}",
        trace_id=result["trace_id"],
        issued_by=profile.function.replace("-", "_"),
        type=profile.command_type,
        payload=payload,
    )


# --- GAP 1: causal signals -------------------------------------------------


def test_hero_demand_confidence_is_derived_from_history_not_hardcoded() -> None:
    full = _scenario()
    _, full_command = _case_command(full, "inventory-rebalancing")

    thin = _scenario()
    hero_skus = thin.hero_style_sku_ids
    # Drop the even-day hero demand so day-over-day coverage halves.
    thin.demand_history = [
        record
        for record in thin.demand_history
        if not (record.sku_id in hero_skus and record.day % 2 == 0)
    ]
    _, thin_command = _case_command(thin, "inventory-rebalancing")

    # With the seeded 14-day history and the active signal the hero clears the
    # 0.7 auto-execute floor, and the value is derived from real coverage:
    # thinning the history lowers it.
    assert 0.7 <= full_command.payload["demand_confidence"] <= 1.0
    assert (
        thin_command.payload["demand_confidence"]
        < full_command.payload["demand_confidence"]
    )


def test_disabling_the_demand_signal_drops_confidence_below_the_auto_floor() -> None:
    active = _scenario()
    _, active_command = _case_command(active, "inventory-rebalancing")

    quiet = _scenario()
    for signal in quiet.demand_signals.values():
        signal.active = False
    _, quiet_command = _case_command(quiet, "inventory-rebalancing")

    assert active_command.payload["demand_confidence"] >= 0.7
    assert quiet_command.payload["demand_confidence"] < 0.7

    # The derived confidence changes the world decision branch: the same
    # auto-approved transfer that executes with the signal is now rejected as a
    # transfer exception that needs an approval reference.
    accepted = active.apply_command(active_command)
    rejected = quiet.apply_command(quiet_command)

    assert accepted.type == "command.accepted"
    assert rejected.type == "command.rejected"
    assert "approval reference" in rejected.payload["reason"]


def test_removing_recent_history_changes_weeks_of_supply_and_velocity() -> None:
    baseline = _scenario()
    _, baseline_command = _case_command(baseline, "demand-spike-response")
    baseline_velocity = baseline_command.payload["regional_velocity_change"]
    baseline_weeks = baseline_command.payload["weeks_of_supply"]

    starved = _scenario()
    # Remove the recent-window (days 8-14) demand for the hero style/region.
    hero_skus = starved.hero_style_sku_ids
    starved.demand_history = [
        record
        for record in starved.demand_history
        if not (record.sku_id in hero_skus and record.day >= 8)
    ]
    _, starved_command = _case_command(starved, "demand-spike-response")

    assert starved_command.payload["regional_velocity_change"] < baseline_velocity
    # Less demand in the denominator means more weeks of cover.
    assert starved_command.payload["weeks_of_supply"] > baseline_weeks


# --- GAP 2: cohort and lifecycle -------------------------------------------


def test_customer_cohort_weighting_changes_derived_demand_evidence() -> None:
    baseline = _scenario()
    _, baseline_command = _case_command(baseline, "demand-spike-response")

    downgraded = _scenario()
    for customer in downgraded.customers.values():
        if customer.region.startswith("UK"):
            customer.cohort = "occasional"
    _, downgraded_command = _case_command(downgraded, "demand-spike-response")

    # Downgrading the UK cohort mix lowers weighted demand, which must move the
    # derived evidence — cohort is not decorative.
    assert (
        downgraded_command.payload["weeks_of_supply"]
        != baseline_command.payload["weeks_of_supply"]
    )


def test_style_lifecycle_gates_markdown_recommendation() -> None:
    eligible = _scenario()
    case, command = _case_command(eligible, "markdown-governance")
    style_id = eligible.markdown_style_id
    assert eligible.styles[style_id].lifecycle in {"sale", "clearance"}
    assert case.recommended_action == "recommend-markdown"

    accepted = eligible.apply_command(command)
    assert accepted.type == "command.accepted"
    assert case.outcome["action"] == "recommend-markdown"

    # A full-price / new-arrival style is not markdown-eligible: the same case
    # now recommends holding full price, and an explicit markdown command is
    # rejected.
    ineligible = _scenario()
    ineligible.styles[ineligible.markdown_style_id].lifecycle = "new-arrival"
    ineligible_case, ineligible_command = _case_command(
        ineligible, "markdown-governance"
    )

    assert ineligible_case.recommended_action == "hold-full-price"
    forced = SimulationCommand(
        command_id="cmd-forced-markdown",
        trace_id=ineligible_command.trace_id,
        issued_by=ineligible_command.issued_by,
        type=ineligible_command.type,
        payload={**ineligible_command.payload, "action": "recommend-markdown"},
    )
    rejected = ineligible.apply_command(forced)
    assert rejected.type == "command.rejected"
    assert "eligible" in rejected.payload["reason"]


# --- GAP 3: real entities and typed mutations ------------------------------


SUPPORTING = [
    workflow_type
    for workflow_type in FASHION_PROCESS_PROFILES
    if workflow_type != "inventory-rebalancing"
]


@pytest.mark.parametrize("workflow_type", SUPPORTING)
def test_supporting_workflow_mutates_a_real_entity(workflow_type: str) -> None:
    scenario = _scenario()
    case, command = _case_command(scenario, workflow_type)

    before = deepcopy(scenario.entity_snapshot(workflow_type, case))
    accepted = scenario.apply_command(command)
    after = scenario.entity_snapshot(workflow_type, case)

    assert accepted.type == "command.accepted"
    # The workflow read and mutated a real, versioned entity.
    assert after != before
    assert after["version"] == before["version"] + 1
    assert case.outcome["source_mode"] == "world-entity"


@pytest.mark.parametrize("workflow_type", SUPPORTING)
def test_supporting_workflow_mutation_is_idempotent(workflow_type: str) -> None:
    scenario = _scenario()
    case, command = _case_command(scenario, workflow_type)

    scenario.apply_command(command)
    after_first = deepcopy(scenario.entity_snapshot(workflow_type, case))
    duplicate = scenario.apply_command(command)
    after_second = scenario.entity_snapshot(workflow_type, case)

    assert duplicate.type == "command.accepted"
    assert after_second == after_first


@pytest.mark.parametrize("workflow_type", SUPPORTING)
def test_supporting_workflow_rejects_unknown_entity(workflow_type: str) -> None:
    scenario = _scenario()
    case, command = _case_command(scenario, workflow_type)

    # Point both the case and the command at a subject that does not resolve to
    # a real world entity; the entity resolver must reject rather than fake a
    # generic pass.
    case.subject_ids = ("GHOST-ENTITY", "GHOST-2")
    bad = SimulationCommand(
        command_id=f"cmd-bad-{workflow_type}",
        trace_id=command.trace_id,
        issued_by=command.issued_by,
        type=command.type,
        payload={**command.payload, "subject_ids": ["GHOST-ENTITY", "GHOST-2"]},
    )
    rejected = scenario.apply_command(bad)

    assert rejected.type == "command.rejected"
    assert "unknown" in rejected.payload["reason"]
    assert case.status == "open"
