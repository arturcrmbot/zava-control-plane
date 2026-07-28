"""Task 2: Static contract assertions for the hospitality vertical pack.

Verifies HOSPITALITY_DOMAINS, HOSPITALITY_FUNCTIONS, HOSPITALITY_AUTHORITY,
HOSPITALITY_PERSONAS, and HOSPITALITY_AGENTS satisfy the design contract
without requiring a full runtime build.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

import pytest

from verticals.hospitality.agents import HOSPITALITY_AGENTS
from verticals.hospitality.authority import HOSPITALITY_AUTHORITY
from verticals.hospitality.domains import HOSPITALITY_DOMAINS
from verticals.hospitality.functions import HOSPITALITY_FUNCTIONS
from verticals.hospitality.personas import HOSPITALITY_PERSONAS

EXPECTED_WORKFLOW_IDS = [
    "hotel-operations-recovery",
    "room-readiness-coordination",
    "asset-maintenance-response",
    "guest-service-recovery",
    "occupancy-pressure-response",
    "workforce-demand-balancing",
    "food-and-beverage-readiness",
    "energy-anomaly-response",
]

# Exact persona -> approval_action mapping from the design
WORKFLOW_APPROVAL_ACTIONS = {
    "hotel-operations-recovery": ("regional_operations_manager", "execute_hotel_recovery"),
    "room-readiness-coordination": ("hotel_general_manager", "apply_room_readiness_plan"),
    "asset-maintenance-response": ("maintenance_manager", "dispatch_maintenance_work_order"),
    "guest-service-recovery": ("guest_recovery_manager", "issue_guest_recovery_action"),
    "occupancy-pressure-response": ("commercial_director", "apply_booking_inventory_plan"),
    "workforce-demand-balancing": ("workforce_planning_manager", "apply_workforce_shift_plan"),
    "food-and-beverage-readiness": ("food_beverage_operations_manager", "apply_food_beverage_service_plan"),
    "energy-anomaly-response": ("sustainability_operations_manager", "apply_energy_control_plan"),
}

# Exact external_event per workflow — convention: {persona_role}_decision
WORKFLOW_EXPECTED_EVENTS: dict[str, str] = {
    "hotel-operations-recovery": "regional_operations_manager_decision",
    "room-readiness-coordination": "hotel_general_manager_decision",
    "asset-maintenance-response": "maintenance_manager_decision",
    "guest-service-recovery": "guest_recovery_manager_decision",
    "occupancy-pressure-response": "commercial_director_decision",
    "workforce-demand-balancing": "workforce_planning_manager_decision",
    "food-and-beverage-readiness": "food_beverage_operations_manager_decision",
    "energy-anomaly-response": "sustainability_operations_manager_decision",
}

# Expected max_value_gbp per agent, from HOSPITALITY_AUTHORITY spend_limit_gbp
# of the primary HITL gate persona for each workflow.
EXPECTED_AGENT_MAX_VALUE_GBP: dict[str, float] = {
    "hotel-operations-recovery": 15_000.0,       # regional_operations_manager
    "room-readiness-coordination": 2_500.0,      # hotel_general_manager
    "asset-maintenance-response": 10_000.0,      # maintenance_manager
    "guest-service-recovery": 2_000.0,           # guest_recovery_manager
    "occupancy-pressure-response": 100_000.0,    # commercial_director
    "workforce-demand-balancing": 5_000.0,       # workforce_planning_manager
    "food-and-beverage-readiness": 5_000.0,      # food_beverage_operations_manager
    "energy-anomaly-response": 25_000.0,         # sustainability_operations_manager
}

ESCALATION_ROLES = {
    "hotel_operations_director",
    "estates_director",
    "people_operations_director",
    "sustainability_director",
}


def test_exact_eight_workflow_ids() -> None:
    assert set(HOSPITALITY_DOMAINS.keys()) == set(EXPECTED_WORKFLOW_IDS), (
        f"Workflow ID mismatch.\n  missing: {set(EXPECTED_WORKFLOW_IDS) - set(HOSPITALITY_DOMAINS)}\n"
        f"  extra: {set(HOSPITALITY_DOMAINS) - set(EXPECTED_WORKFLOW_IDS)}"
    )


def test_domains_are_non_stub() -> None:
    for wf_id, domain in HOSPITALITY_DOMAINS.items():
        assert not domain.stub, f"Domain {wf_id!r} must not be a stub"


def test_domains_have_unique_workflow_id_prefixes() -> None:
    prefixes = [d.workflow_id_prefix for d in HOSPITALITY_DOMAINS.values()]
    assert len(prefixes) == len(set(prefixes)), (
        f"Duplicate workflow_id_prefix values: {prefixes}"
    )


def test_domains_have_unique_orchestrator_names() -> None:
    names = [d.orchestrator_name for d in HOSPITALITY_DOMAINS.values()]
    assert len(names) == len(set(names)), (
        f"Duplicate orchestrator_name values: {names}"
    )


def test_domains_each_have_at_least_one_deterministic_phase() -> None:
    for wf_id, domain in HOSPITALITY_DOMAINS.items():
        kinds = {p.kind for p in domain.phases}
        assert "deterministic" in kinds, (
            f"Domain {wf_id!r} has no deterministic phase"
        )


def test_domains_each_have_at_least_one_agent_phase() -> None:
    for wf_id, domain in HOSPITALITY_DOMAINS.items():
        kinds = {p.kind for p in domain.phases}
        assert "agent" in kinds, (
            f"Domain {wf_id!r} has no agent phase"
        )


def test_domains_have_valid_owning_function() -> None:
    for wf_id, domain in HOSPITALITY_DOMAINS.items():
        assert domain.function is not None, (
            f"Domain {wf_id!r} has no owning function set"
        )
        assert domain.function in HOSPITALITY_FUNCTIONS, (
            f"Domain {wf_id!r} function {domain.function!r} not in HOSPITALITY_FUNCTIONS"
        )


def test_domain_hitl_personas_are_registered() -> None:
    for wf_id, domain in HOSPITALITY_DOMAINS.items():
        for gate in domain.hitl_gates:
            assert gate.persona in HOSPITALITY_PERSONAS, (
                f"Domain {wf_id!r} HITL gate persona {gate.persona!r} not in HOSPITALITY_PERSONAS"
            )


def test_function_ownership_covers_each_domain_exactly_once() -> None:
    covered: dict[str, list[str]] = defaultdict(list)
    for fn_name, fn in HOSPITALITY_FUNCTIONS.items():
        for wf_id in fn.owns_domains:
            covered[wf_id].append(fn_name)

    # every domain is covered
    for wf_id in EXPECTED_WORKFLOW_IDS:
        assert wf_id in covered, f"Domain {wf_id!r} not owned by any function"
        assert len(covered[wf_id]) == 1, (
            f"Domain {wf_id!r} owned by multiple functions: {covered[wf_id]}"
        )

    # no extra domains
    for wf_id in covered:
        assert wf_id in set(EXPECTED_WORKFLOW_IDS), (
            f"Function owns unknown domain {wf_id!r}"
        )


def _collect_persona_tree_roles(tree) -> set[str]:
    roles = {tree.role}
    for subtree in tree.manages:
        roles |= _collect_persona_tree_roles(subtree)
    return roles


def test_function_persona_hierarchy_roles_exist_in_personas() -> None:
    for fn_name, fn in HOSPITALITY_FUNCTIONS.items():
        roles = _collect_persona_tree_roles(fn.persona_hierarchy)
        for role in roles:
            assert role in HOSPITALITY_PERSONAS, (
                f"Function {fn_name!r} persona hierarchy role {role!r} not in HOSPITALITY_PERSONAS"
            )


def test_every_persona_has_matching_authority() -> None:
    for role in HOSPITALITY_PERSONAS:
        assert role in HOSPITALITY_AUTHORITY, (
            f"Persona {role!r} has no matching AuthorityRow in HOSPITALITY_AUTHORITY"
        )


def test_authority_delegation_targets_exist() -> None:
    for role, row in HOSPITALITY_AUTHORITY.items():
        if row.delegate_to is not None:
            assert row.delegate_to in HOSPITALITY_AUTHORITY, (
                f"Authority row {role!r} delegates to {row.delegate_to!r} which is not in HOSPITALITY_AUTHORITY"
            )


def test_authority_delegation_no_cycles() -> None:
    for start_role in HOSPITALITY_AUTHORITY:
        visited = set()
        current = start_role
        while current is not None:
            assert current not in visited, (
                f"Delegation cycle detected starting at {start_role!r}, revisited {current!r}"
            )
            visited.add(current)
            current = HOSPITALITY_AUTHORITY[current].delegate_to


def test_escalation_roles_present_in_authority() -> None:
    for role in ESCALATION_ROLES:
        assert role in HOSPITALITY_AUTHORITY, (
            f"Required escalation role {role!r} missing from HOSPITALITY_AUTHORITY"
        )


def test_approval_actions_match_design_mapping() -> None:
    for wf_id, (persona_role, expected_action) in WORKFLOW_APPROVAL_ACTIONS.items():
        assert persona_role in HOSPITALITY_AUTHORITY, (
            f"Persona {persona_role!r} for workflow {wf_id!r} not in HOSPITALITY_AUTHORITY"
        )
        row = HOSPITALITY_AUTHORITY[persona_role]
        assert expected_action in row.approval_actions, (
            f"Approval action {expected_action!r} not in {persona_role!r}.approval_actions "
            f"(got {row.approval_actions!r})"
        )


def test_one_agent_per_workflow() -> None:
    agent_ids = set(HOSPITALITY_AGENTS.keys())
    expected_ids = set(EXPECTED_WORKFLOW_IDS)
    assert agent_ids == expected_ids, (
        f"Agent IDs must match workflow IDs exactly.\n"
        f"  missing: {expected_ids - agent_ids}\n"
        f"  extra: {agent_ids - expected_ids}"
    )


def test_agents_have_non_empty_allowed_tools() -> None:
    for agent_id, entry in HOSPITALITY_AGENTS.items():
        assert entry.allowed_tools, (
            f"Agent {agent_id!r} has empty allowed_tools"
        )


def test_agent_tools_prefixed_hospitality() -> None:
    for agent_id, entry in HOSPITALITY_AGENTS.items():
        for tool in entry.allowed_tools:
            assert tool.startswith("hospitality_"), (
                f"Agent {agent_id!r} tool {tool!r} must be prefixed 'hospitality_'"
            )


def test_agent_scope_function_matches_declared_function() -> None:
    for agent_id, entry in HOSPITALITY_AGENTS.items():
        assert entry.scope_function in HOSPITALITY_FUNCTIONS, (
            f"Agent {agent_id!r} scope_function {entry.scope_function!r} "
            f"not in HOSPITALITY_FUNCTIONS"
        )


def test_agent_scope_function_equals_owning_function() -> None:
    """Each workflow-keyed agent's scope_function must equal the unique Function
    that owns that workflow (not merely any declared function)."""
    domain_to_fn = {
        wf_id: fn_name
        for fn_name, fn in HOSPITALITY_FUNCTIONS.items()
        for wf_id in fn.owns_domains
    }
    for agent_id, entry in HOSPITALITY_AGENTS.items():
        expected = domain_to_fn.get(agent_id)
        assert expected is not None, (
            f"Agent {agent_id!r} has no owning function in HOSPITALITY_FUNCTIONS"
        )
        assert entry.scope_function == expected, (
            f"Agent {agent_id!r} scope_function={entry.scope_function!r} "
            f"but the owning function for this workflow is {expected!r}"
        )


def test_every_domain_has_at_least_one_hitl_gate() -> None:
    for wf_id, domain in HOSPITALITY_DOMAINS.items():
        assert domain.hitl_gates, (
            f"Domain {wf_id!r} has no HITL gates"
        )


def test_hitl_gate_phases_resolve_to_declared_hitl_phase() -> None:
    for wf_id, domain in HOSPITALITY_DOMAINS.items():
        hitl_phase_names = {p.name for p in domain.phases if p.kind == "hitl"}
        for gate in domain.hitl_gates:
            assert gate.gate_phase in hitl_phase_names, (
                f"Domain {wf_id!r} gate_phase={gate.gate_phase!r} does not resolve "
                f"to a declared Phase(kind='hitl'). "
                f"HITL phases: {sorted(hitl_phase_names)}"
            )


EXPECTED_PERSONA_ROLES = frozenset({
    "hotel_general_manager",
    "regional_operations_manager",
    "hotel_operations_director",
    "maintenance_manager",
    "estates_director",
    "guest_recovery_manager",
    "commercial_director",
    "workforce_planning_manager",
    "people_operations_director",
    "food_beverage_operations_manager",
    "sustainability_operations_manager",
    "sustainability_director",
})


def test_hospitality_personas_exact_12_role_set() -> None:
    assert set(HOSPITALITY_PERSONAS.keys()) == EXPECTED_PERSONA_ROLES, (
        f"HOSPITALITY_PERSONAS role set mismatch.\n"
        f"  missing: {EXPECTED_PERSONA_ROLES - set(HOSPITALITY_PERSONAS)}\n"
        f"  extra: {set(HOSPITALITY_PERSONAS) - EXPECTED_PERSONA_ROLES}"
    )


def test_hospitality_authority_exact_12_role_set() -> None:
    assert set(HOSPITALITY_AUTHORITY.keys()) == EXPECTED_PERSONA_ROLES, (
        f"HOSPITALITY_AUTHORITY role set mismatch.\n"
        f"  missing: {EXPECTED_PERSONA_ROLES - set(HOSPITALITY_AUTHORITY)}\n"
        f"  extra: {set(HOSPITALITY_AUTHORITY) - EXPECTED_PERSONA_ROLES}"
    )


# ---------------------------------------------------------------------------
# HITL gate exact-pin tests
# ---------------------------------------------------------------------------

def _check_hitl_personas(domains: dict) -> list[str]:
    """Returns error strings for any HITL gate persona that deviates from WORKFLOW_APPROVAL_ACTIONS."""
    errors = []
    for wf_id, (expected_persona, _) in WORKFLOW_APPROVAL_ACTIONS.items():
        domain = domains[wf_id]
        actual = domain.hitl_gates[0].persona
        if actual != expected_persona:
            errors.append(f"{wf_id!r}: gate.persona={actual!r}, expected {expected_persona!r}")
    return errors


def _check_hitl_events(domains: dict) -> list[str]:
    """Returns error strings for any HITL gate external_event that deviates from WORKFLOW_EXPECTED_EVENTS."""
    errors = []
    for wf_id, expected_event in WORKFLOW_EXPECTED_EVENTS.items():
        domain = domains[wf_id]
        actual = domain.hitl_gates[0].external_event
        if actual != expected_event:
            errors.append(f"{wf_id!r}: gate.external_event={actual!r}, expected {expected_event!r}")
    return errors


def test_each_workflow_has_exactly_one_hitl_gate() -> None:
    for wf_id, domain in HOSPITALITY_DOMAINS.items():
        assert len(domain.hitl_gates) == 1, (
            f"Domain {wf_id!r} must have exactly one HITL gate for this release "
            f"(got {len(domain.hitl_gates)})"
        )


def test_hitl_gate_persona_matches_workflow_approval_actions() -> None:
    errors = _check_hitl_personas(HOSPITALITY_DOMAINS)
    assert not errors, "HITL gate persona mismatch:\n" + "\n".join(errors)


def test_hitl_gate_external_event_is_exact() -> None:
    errors = _check_hitl_events(HOSPITALITY_DOMAINS)
    assert not errors, "HITL gate external_event mismatch:\n" + "\n".join(errors)


def test_hitl_gate_persona_drift_detected_via_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """RED proof: persona check catches drift injected via monkeypatch."""
    import verticals.hospitality.domains as domains_mod

    original = HOSPITALITY_DOMAINS["hotel-operations-recovery"]
    bad_gate = replace(original.hitl_gates[0], persona="wrong_persona")
    bad_domain = replace(original, hitl_gates=(bad_gate,))
    monkeypatch.setitem(domains_mod.HOSPITALITY_DOMAINS, "hotel-operations-recovery", bad_domain)

    errors = _check_hitl_personas(domains_mod.HOSPITALITY_DOMAINS)
    assert errors, "RED proof: drift must produce at least one error"
    assert any("hotel-operations-recovery" in e for e in errors), (
        f"Expected hotel-operations-recovery in errors, got: {errors}"
    )


def test_hitl_gate_event_drift_detected_via_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """RED proof: external_event check catches drift injected via monkeypatch."""
    import verticals.hospitality.domains as domains_mod

    original = HOSPITALITY_DOMAINS["room-readiness-coordination"]
    bad_gate = replace(original.hitl_gates[0], external_event="wrong_event")
    bad_domain = replace(original, hitl_gates=(bad_gate,))
    monkeypatch.setitem(domains_mod.HOSPITALITY_DOMAINS, "room-readiness-coordination", bad_domain)

    errors = _check_hitl_events(domains_mod.HOSPITALITY_DOMAINS)
    assert errors, "RED proof: drift must produce at least one error"
    assert any("room-readiness-coordination" in e for e in errors), (
        f"Expected room-readiness-coordination in errors, got: {errors}"
    )


# ---------------------------------------------------------------------------
# Agent spend-limit tests
# ---------------------------------------------------------------------------

def test_no_agent_is_unbounded() -> None:
    for agent_id, entry in HOSPITALITY_AGENTS.items():
        assert entry.max_value_gbp is not None, (
            f"Agent {agent_id!r} must have a max_value_gbp spend limit (got None)"
        )


def test_agent_max_value_gbp_matches_authority() -> None:
    for agent_id, expected_limit in EXPECTED_AGENT_MAX_VALUE_GBP.items():
        entry = HOSPITALITY_AGENTS[agent_id]
        assert entry.max_value_gbp == expected_limit, (
            f"Agent {agent_id!r} max_value_gbp={entry.max_value_gbp!r} "
            f"but HOSPITALITY_AUTHORITY expects {expected_limit!r}"
        )
