from __future__ import annotations

from verticals.telco.mcp_tools import (
    commercial,
    network,
    operations,
    twin,
)
from verticals.telco.mcp_tools.common import (
    prepare_action_result,
    simulator_result,
)
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES


EXPECTED_TOOLS = {
    "network_query_state",
    "network_query_impact",
    "network_validate_action",
    "network_prepare_action",
    "operations_query_case",
    "operations_search_runbook",
    "operations_match_resources",
    "operations_prepare_case_action",
    "commercial_query_customer",
    "commercial_query_order_revenue",
    "commercial_evaluate_entitlement",
    "commercial_prepare_action",
    "twin_forecast",
    "twin_compare_scenarios",
    "twin_query_external_signal",
    "twin_publish_plan",
}


def test_four_capability_modules_expose_only_the_shared_tool_contract():
    actual = (
        network.TOOL_NAMES
        | operations.TOOL_NAMES
        | commercial.TOOL_NAMES
        | twin.TOOL_NAMES
    )

    assert actual == EXPECTED_TOOLS
    assert len(actual) == 16


def test_simulator_results_always_include_world_provenance():
    result = simulator_result(
        {"status": "degraded"},
        actor_ids=["AST-SITE-01-radio-unit"],
        event_ids=["evt-00000042"],
        trace_id="trace-42",
        as_of_sim_time=12.5,
    )

    assert result == {
        "data": {"status": "degraded"},
        "source_mode": "simulated",
        "actor_ids": ["AST-SITE-01-radio-unit"],
        "event_ids": ["evt-00000042"],
        "trace_id": "trace-42",
        "as_of_sim_time": 12.5,
    }


def test_prepare_action_returns_a_proposal_without_mutating_input():
    observation = {"case_id": "CASE-1", "allowed_actions": ["resolve_case"]}

    result = prepare_action_result(
        observation,
        action="resolve_case",
        payload={"case_id": "CASE-1"},
        actor_ids=["CASE-1"],
        event_ids=["evt-1"],
        trace_id="trace-1",
        as_of_sim_time=3.0,
    )

    assert observation == {
        "case_id": "CASE-1",
        "allowed_actions": ["resolve_case"],
    }
    assert result["data"]["command_proposal"] == {
        "type": "resolve_case",
        "payload": {"case_id": "CASE-1"},
    }
    assert result["source_mode"] == "simulated"


def test_every_profile_tool_resolves_to_one_capability_module():
    actual = (
        network.TOOL_NAMES
        | operations.TOOL_NAMES
        | commercial.TOOL_NAMES
        | twin.TOOL_NAMES
    )

    for profile in STANDARD_PROCESS_PROFILES.values():
        assert set(profile.allowed_tools) <= actual
