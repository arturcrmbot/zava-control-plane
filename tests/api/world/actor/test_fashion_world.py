from copy import deepcopy

import pytest

from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.world import DEMO_SEED, FashionScenario


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
        ("quantity", 10_000, "insufficient physically available stock"),
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
    """A high-value (non-safety-stock) exception is only executable behind a
    fully authorised approval: an exact Fashion authority role whose
    approval actions cover this workflow, a spend limit that covers the
    retail value, an issuer distinct from the approver, and an approved
    source version matching the current one."""
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
            "approval_reference": "approval:merchandising_director:001",
            "approval_role": "merchandising_director",
            "approved_source_version": source.version,
        },
    )

    accepted = scenario.apply_command(governed)

    assert accepted.type == "command.accepted"
    assert case.outcome["governance"] == {
        "policy_decision": "approval_required",
        "approval_reference": "approval:merchandising_director:001",
    }


def _high_value_exception_case(
    scenario: FashionScenario,
) -> tuple[object, SimulationCommand, object]:
    """Build an inventory-rebalancing command whose only binding constraint
    is the general transfer-exception rule (quantity > 50), with safety
    stock left wide open so only the generic governed-transfer-approval
    path is exercised (not the safety-stock breach path)."""
    case, command = _case_command(scenario, "inventory-rebalancing")
    source = scenario.inventory[command.payload["source_position_id"]]
    source.on_hand = 1000
    source.reserved = 0
    source.presentation_minimum = 0
    source.safety_stock = 0
    return case, command, source


def test_high_value_transfer_rejects_a_free_form_or_unknown_approval_role() -> None:
    """A high-value exception must authenticate the approval the same way a
    safety-stock breach does: an unrecognised / free-form role string must
    not stand in for a genuine Fashion authority persona."""
    scenario = _scenario()
    case, command, source = _high_value_exception_case(scenario)
    unauthorized = _with_payload(
        command,
        command_id="cmd-highvalue-unknown-role",
        quantity=60,
        policy_decision="approval_required",
        approval_reference="approval:merchandising-director:001",
        approval_role="merchandising-director",  # hyphenated: not an authority key
        approved_source_version=source.version,
    )

    rejected = scenario.apply_command(unauthorized)

    assert rejected.type == "command.rejected"
    assert "authorized persona" in rejected.payload["reason"]
    assert source.on_hand == 1000
    assert case.status == "open"


def test_high_value_transfer_rejects_self_approval() -> None:
    """Self-approval is an identity match between the recommendation's
    persona (``recommended_by``) and the approving persona
    (``approval_role``) — the SAME Fashion authority-persona namespace.
    ``issued_by`` stays the function label (a disjoint namespace used only
    by ``CommandGateway`` for objective ownership) and must NOT be the
    field compared here, or the guard is dead on the real Durable path."""
    scenario = _scenario()
    case, command, source = _high_value_exception_case(scenario)
    self_approved = SimulationCommand(
        command_id="cmd-highvalue-self-approval",
        trace_id=command.trace_id,
        issued_by=command.issued_by,
        type=command.type,
        payload={
            **command.payload,
            "quantity": 60,
            "policy_decision": "approval_required",
            "approval_reference": "approval:merchandising_director:hv-001",
            "recommended_by": "merchandising_director",
            "approval_role": "merchandising_director",
            "approved_source_version": source.version,
        },
    )

    rejected = scenario.apply_command(self_approved)

    assert rejected.type == "command.rejected"
    assert "self" in rejected.payload["reason"]
    assert source.on_hand == 1000
    assert case.status == "open"


def test_high_value_transfer_rejects_approval_exceeding_persona_spend_limit() -> None:
    scenario = _scenario()
    case, command, source = _high_value_exception_case(scenario)
    sku = scenario.skus[source.sku_id]
    style = scenario.styles[sku.style_id]
    style.unit_retail_gbp = 25_000.0
    # 60 * GBP 25,000 = GBP 1,500,000 exceeds merchandising_director's
    # GBP 1,000,000 spend limit.
    over_limit = _with_payload(
        command,
        command_id="cmd-highvalue-over-limit",
        quantity=60,
        policy_decision="approval_required",
        approval_reference="approval:merchandising_director:hv-002",
        approval_role="merchandising_director",
        approved_source_version=source.version,
    )

    rejected = scenario.apply_command(over_limit)

    assert rejected.type == "command.rejected"
    assert "spend limit" in rejected.payload["reason"]
    assert source.on_hand == 1000
    assert case.status == "open"


def test_high_value_transfer_rejects_a_stale_approved_source_version() -> None:
    scenario = _scenario()
    case, command, source = _high_value_exception_case(scenario)
    stale = _with_payload(
        command,
        command_id="cmd-highvalue-stale",
        quantity=60,
        policy_decision="approval_required",
        approval_reference="approval:merchandising_director:hv-003",
        approval_role="merchandising_director",
        approved_source_version=source.version - 1,
    )

    rejected = scenario.apply_command(stale)

    assert rejected.type == "command.rejected"
    assert "stale" in rejected.payload["reason"]
    assert source.on_hand == 1000
    assert case.status == "open"


def test_high_value_transfer_accepts_a_valid_non_self_authorized_approval() -> None:
    scenario = _scenario()
    case, command, source = _high_value_exception_case(scenario)
    destination = scenario.inventory[command.payload["destination_position_id"]]
    destination_before = destination.on_hand
    approved = _with_payload(
        command,
        command_id="cmd-highvalue-valid",
        quantity=60,
        policy_decision="approval_required",
        approval_reference="approval:merchandising_director:hv-004",
        approval_role="merchandising_director",
        approved_source_version=source.version,
    )

    accepted = scenario.apply_command(approved)

    assert accepted.type == "command.accepted"
    assert case.status == "completed"
    assert source.on_hand == 1000 - 60
    assert destination.on_hand == destination_before + 60


def _safety_stock_case(
    scenario: FashionScenario,
    *,
    on_hand: int = 40,
    reserved: int = 0,
    presentation_minimum: int = 0,
    safety_stock: int = 20,
) -> tuple[object, SimulationCommand, object]:
    """Build an inventory-rebalancing command against a source position whose
    only binding constraint is the protected safety-stock buffer.

    With the defaults, available_to_transfer == 20 and physically_available
    == 40, so a quantity in (20, 40] breaches safety stock without tripping
    any other exception (retail < GBP 10k, quantity <= 50, same country)."""
    case, command = _case_command(scenario, "inventory-rebalancing")
    source = scenario.inventory[command.payload["source_position_id"]]
    source.on_hand = on_hand
    source.reserved = reserved
    source.presentation_minimum = presentation_minimum
    source.safety_stock = safety_stock
    return case, command, source


def _with_payload(command: SimulationCommand, **overrides) -> SimulationCommand:
    return SimulationCommand(
        command_id=command.command_id,
        trace_id=command.trace_id,
        issued_by=command.issued_by,
        type=command.type,
        payload={**command.payload, **overrides},
    )


def test_safety_stock_breach_without_approval_routes_to_hitl_and_blocks() -> None:
    scenario = _scenario()
    case, command, source = _safety_stock_case(scenario)
    before = deepcopy(source)
    assert source.available_to_transfer == 20
    breaching = _with_payload(
        command,
        command_id="cmd-safety-no-approval",
        quantity=30,
        policy_decision="auto_approved",
        approval_reference=None,
    )

    rejected = scenario.apply_command(breaching)

    assert rejected.type == "command.rejected"
    assert "safety-stock breach requires approval" in rejected.payload["reason"]
    assert source == before
    assert case.status == "open"


def test_safety_stock_breach_with_authorized_approval_executes() -> None:
    scenario = _scenario()
    case, command, source = _safety_stock_case(scenario)
    destination = scenario.inventory[command.payload["destination_position_id"]]
    destination_before = destination.on_hand
    approved = _with_payload(
        command,
        command_id="cmd-safety-approved",
        quantity=30,
        policy_decision="approval_required",
        approval_reference="approval:merchandising_director:ss-001",
        approval_role="merchandising_director",
        approved_source_version=source.version,
    )

    accepted = scenario.apply_command(approved)

    assert accepted.type == "command.accepted"
    assert case.status == "completed"
    assert source.on_hand == 10
    assert destination.on_hand == destination_before + 30
    # The transfer consumed protected buffer but never breached the physical
    # floor: on_hand - reserved - presentation_minimum stays non-negative.
    assert source.physically_available >= 0
    assert source.available_to_transfer == 0
    assert case.outcome["governance"] == {
        "policy_decision": "approval_required",
        "approval_reference": "approval:merchandising_director:ss-001",
    }


def test_safety_stock_breach_self_approval_is_blocked() -> None:
    """The recommendation's persona (``recommended_by``) cannot be its own
    safety-stock approver (``approval_role``) — both are Fashion
    authority-persona role strings in the same namespace. ``issued_by``
    (the function label ``CommandGateway`` matches to the claimed
    objective) is a disjoint identity and is deliberately left as the
    real function label here to prove the guard does not depend on it."""
    scenario = _scenario()
    case, command, source = _safety_stock_case(scenario)
    before = deepcopy(source)
    # Same persona recommended and "approved" this exception — self-approval.
    self_approved = SimulationCommand(
        command_id="cmd-self-approval",
        trace_id=command.trace_id,
        issued_by=command.issued_by,
        type=command.type,
        payload={
            **command.payload,
            "quantity": 30,
            "policy_decision": "approval_required",
            "approval_reference": "approval:merchandising_director:self-001",
            "recommended_by": "merchandising_director",
            "approval_role": "merchandising_director",
            "approved_source_version": source.version,
        },
    )

    rejected = scenario.apply_command(self_approved)

    assert rejected.type == "command.rejected"
    assert "self" in rejected.payload["reason"]
    assert source == before
    assert case.status == "open"


def test_safety_stock_breach_missing_recommender_identity_is_blocked() -> None:
    """A governed exception with no auditable recommender identity must
    fail closed — an otherwise well-formed, authorised, non-stale approval
    must not be able to execute when ``recommended_by`` is missing."""
    scenario = _scenario()
    case, command, source = _safety_stock_case(scenario)
    before = deepcopy(source)
    missing_recommender = _with_payload(
        command,
        command_id="cmd-safety-missing-recommender",
        quantity=30,
        policy_decision="approval_required",
        approval_reference="approval:merchandising_director:ss-005",
        recommended_by=None,
        approval_role="merchandising_director",
        approved_source_version=source.version,
    )

    rejected = scenario.apply_command(missing_recommender)

    assert rejected.type == "command.rejected"
    assert "recommender identity" in rejected.payload["reason"]
    assert source == before
    assert case.status == "open"


def test_safety_stock_breach_with_unauthorized_persona_is_blocked() -> None:
    scenario = _scenario()
    case, command, source = _safety_stock_case(scenario)
    before = deepcopy(source)
    unauthorized = _with_payload(
        command,
        command_id="cmd-safety-unauthorized",
        quantity=30,
        policy_decision="approval_required",
        approval_reference="approval:returns_operations_manager:ss-002",
        approval_role="returns_operations_manager",
        approved_source_version=source.version,
    )

    rejected = scenario.apply_command(unauthorized)

    assert rejected.type == "command.rejected"
    assert "authorized persona" in rejected.payload["reason"]
    assert source == before
    assert case.status == "open"


def test_safety_stock_breach_with_stale_approval_is_blocked() -> None:
    scenario = _scenario()
    case, command, source = _safety_stock_case(scenario)
    before = deepcopy(source)
    stale = _with_payload(
        command,
        command_id="cmd-safety-stale",
        quantity=30,
        policy_decision="approval_required",
        approval_reference="approval:merchandising_director:ss-003",
        approval_role="merchandising_director",
        approved_source_version=source.version - 1,
    )

    rejected = scenario.apply_command(stale)

    assert rejected.type == "command.rejected"
    assert "stale" in rejected.payload["reason"]
    assert source == before
    assert case.status == "open"


def test_transfer_beyond_physical_availability_is_hard_rejected_even_with_approval() -> None:
    scenario = _scenario()
    case, command, source = _safety_stock_case(scenario)
    before = deepcopy(source)
    # physically_available == 40; 41 would drive the physical floor negative,
    # so no approval can authorise it.
    over_physical = _with_payload(
        command,
        command_id="cmd-over-physical",
        quantity=41,
        policy_decision="approval_required",
        approval_reference="approval:merchandising_director:ss-004",
        approval_role="merchandising_director",
        approved_source_version=source.version,
    )

    rejected = scenario.apply_command(over_physical)

    assert rejected.type == "command.rejected"
    assert "insufficient physically available stock" in rejected.payload["reason"]
    assert source == before
    assert case.status == "open"


def test_no_action_records_binding_constraints_without_moving_stock() -> None:
    scenario = _scenario()
    case, command = _case_command(scenario, "inventory-rebalancing")
    source = scenario.inventory[command.payload["source_position_id"]]
    destination = scenario.inventory[command.payload["destination_position_id"]]
    before = (deepcopy(source), deepcopy(destination))
    no_action = SimulationCommand(
        command_id="cmd-no-action",
        trace_id=command.trace_id,
        issued_by=command.issued_by,
        type=command.type,
        payload={
            **command.payload,
            "action": "no-action",
            "quantity": 0,
            "evaluated_candidates": [
                {
                    "source_position_id": source.id,
                    "destination_position_id": destination.id,
                }
            ],
            "binding_constraints": ["transfer-cost"],
            "kpi_comparison": {
                "expected_recovered_margin_gbp": 100.0,
                "transfer_cost_gbp": 200.0,
            },
        },
    )

    accepted = scenario.apply_command(no_action)

    assert accepted.type == "command.accepted"
    assert (source, destination) == before
    assert case.outcome["action"] == "no-action"
    assert case.outcome["binding_constraints"] == ["transfer-cost"]
    assert case.outcome["evaluation"]["status"] == "pass"


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


def test_demo_factory_defaults_to_canonical_seed_42() -> None:
    scenario = FashionScenario.demo()
    scenario.install()

    assert scenario.runtime.seed == DEMO_SEED
    assert DEMO_SEED == 42


def test_customers_have_explicit_cohort_assignments() -> None:
    scenario = _scenario()
    cohorts = {customer.cohort for customer in scenario.customers.values()}

    assert len(cohorts) >= 2
    assert all(customer.cohort for customer in scenario.customers.values())
    assert len(scenario.customers) == 300


def test_styles_have_explicit_lifecycle_stage() -> None:
    scenario = _scenario()
    lifecycles = {style.lifecycle for style in scenario.styles.values()}

    assert len(lifecycles) >= 2
    assert all(style.lifecycle for style in scenario.styles.values())
    assert len(scenario.styles) == 24
