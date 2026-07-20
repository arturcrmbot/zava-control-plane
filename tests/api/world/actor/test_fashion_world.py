from copy import deepcopy

import pytest

from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.world import FashionScenario


def _scenario(seed: int = 20260720) -> FashionScenario:
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


def test_demo_scale_is_deterministic_and_matches_the_approved_actor_world() -> None:
    first = _scenario()
    second = _scenario()

    assert len(first.stores) == 8
    assert len(first.distribution_centres) == 2
    assert len(first.brands) == 12
    assert len(first.styles) == 24
    assert len(first.skus) == 192
    assert len(first.customers) == 300
    assert {row.day for row in first.demand_history} == set(range(1, 15))
    assert first.render_state() == second.render_state()
    assert first.runtime.canonical_journal() == second.runtime.canonical_journal()


def test_policy_safe_owned_transfer_mutates_versions_and_is_idempotent() -> None:
    scenario = _scenario()
    case, command = _case_command(scenario, "inventory-rebalancing")
    source = scenario.inventory[command.payload["source_position_id"]]
    destination = scenario.inventory[command.payload["destination_position_id"]]
    source_before = deepcopy(source)
    destination_before = deepcopy(destination)

    accepted = scenario.apply_command(command)
    journal_size = len(scenario.runtime.journal)
    duplicate = scenario.apply_command(command)

    assert accepted.type == "command.accepted"
    assert duplicate is accepted
    assert len(scenario.runtime.journal) == journal_size
    assert source.on_hand == source_before.on_hand - command.payload["quantity"]
    assert destination.on_hand == destination_before.on_hand + command.payload["quantity"]
    assert source.version == source_before.version + 1
    assert destination.version == destination_before.version + 1
    assert case.status == "completed"
    assert case.outcome["evaluation"]["status"] == "pass"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("expected_source_version", -1, "stale source version"),
        ("ownership", "marketplace", "ineligible ownership"),
        ("quantity", 10_000, "insufficient available stock"),
    ],
)
def test_inventory_transfer_rejections_preserve_source_state(
    field: str,
    value: object,
    reason: str,
) -> None:
    scenario = _scenario()
    case, command = _case_command(scenario, "inventory-rebalancing")
    source = scenario.inventory[command.payload["source_position_id"]]
    before = deepcopy(source)
    invalid = SimulationCommand(
        command_id=f"cmd-invalid-{field}",
        trace_id=command.trace_id,
        issued_by=command.issued_by,
        type=command.type,
        payload={**command.payload, field: value},
    )

    rejected = scenario.apply_command(invalid)

    assert rejected.type == "command.rejected"
    assert reason in rejected.payload["reason"]
    assert source == before
    assert case.status == "open"


def test_high_value_transfer_requires_an_explicit_approval_reference() -> None:
    scenario = _scenario()
    case, command = _case_command(scenario, "inventory-rebalancing")
    source = scenario.inventory[command.payload["source_position_id"]]
    source.on_hand = 1000
    high_value = SimulationCommand(
        command_id="cmd-high-value",
        trace_id=command.trace_id,
        issued_by=command.issued_by,
        type=command.type,
        payload={
            **command.payload,
            "quantity": 100,
            "policy_decision": "approval_required",
            "approval_reference": None,
        },
    )

    rejected = scenario.apply_command(high_value)

    assert rejected.type == "command.rejected"
    assert "approval reference" in rejected.payload["reason"]
    assert case.status == "open"


def test_approved_high_value_transfer_preserves_governance_evidence() -> None:
    scenario = _scenario()
    case, command = _case_command(scenario, "inventory-rebalancing")
    source = scenario.inventory[command.payload["source_position_id"]]
    source.on_hand = 1000
    governed = SimulationCommand(
        command_id="cmd-governed-high-value",
        trace_id=command.trace_id,
        issued_by=command.issued_by,
        type=command.type,
        payload={
            **command.payload,
            "quantity": 100,
            "policy_decision": "approval_required",
            "approval_reference": "approval:merchandising-director:001",
        },
    )

    accepted = scenario.apply_command(governed)

    assert accepted.type == "command.accepted"
    assert case.outcome["governance"] == {
        "policy_decision": "approval_required",
        "approval_reference": "approval:merchandising-director:001",
    }


@pytest.mark.parametrize(
    "workflow_type",
    [
        workflow_type
        for workflow_type in FASHION_PROCESS_PROFILES
        if workflow_type != "inventory-rebalancing"
    ],
)
def test_each_supporting_workflow_executes_a_distinct_typed_mutation(
    workflow_type: str,
) -> None:
    scenario = _scenario()
    case, command = _case_command(scenario, workflow_type)
    profile = FASHION_PROCESS_PROFILES[workflow_type]

    accepted = scenario.apply_command(command)

    assert accepted.type == "command.accepted"
    assert case.status == "completed"
    assert case.outcome["command_type"] == profile.command_type
    assert case.outcome["mutation_family"] == profile.mutation_family
    assert any(
        event.type == profile.success_event
        and event.trace_id == command.trace_id
        for event in scenario.runtime.journal
    )


def test_markdown_governance_records_a_recommendation_without_price_mutation() -> None:
    scenario = _scenario()
    case, command = _case_command(scenario, "markdown-governance")
    prices_before = {
        style.id: style.unit_retail_gbp for style in scenario.styles.values()
    }

    scenario.apply_command(command)

    assert case.outcome["action"] == "recommend-markdown"
    assert {
        style.id: style.unit_retail_gbp for style in scenario.styles.values()
    } == prices_before
