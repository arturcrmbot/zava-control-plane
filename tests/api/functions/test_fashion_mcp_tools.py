import json

import pytest

from verticals.fashion.mcp_tools import retail
from verticals.fashion.mcp_tools.common import (
    FashionCommandParams,
    FashionEvidenceParams,
    command_result,
    evidence_result,
)


EXPECTED_TOOLS = {
    "fashion_query_demand",
    "fashion_query_inventory",
    "fashion_query_orders",
    "fashion_query_partners",
    "fashion_query_policies",
    "fashion_query_returns",
    "fashion_prepare_command",
}


def test_fashion_mcp_module_exposes_the_complete_pack_contract() -> None:
    assert retail.TOOL_NAMES == EXPECTED_TOOLS


def test_fashion_evidence_results_preserve_world_provenance() -> None:
    params = FashionEvidenceParams(
        evidence={"status": "imbalanced"},
        actor_ids=["INV-001"],
        event_ids=["evt-00000001"],
        trace_id="trace-fashion-1",
        as_of_sim_time=14.0,
    )

    result = json.loads(
        evidence_result(params, operation="query_inventory").text_result_for_llm
    )

    assert result == {
        "data": {
            "operation": "query_inventory",
            "status": "imbalanced",
        },
        "source_mode": "simulated",
        "actor_ids": ["INV-001"],
        "event_ids": ["evt-00000001"],
        "trace_id": "trace-fashion-1",
        "as_of_sim_time": 14.0,
    }


def test_prepare_command_fails_closed_without_an_explicit_allow_list() -> None:
    params = FashionCommandParams(
        workflow_id="WF-1",
        command_id="CMD-1",
        command_type="unknown.command",
        payload={},
        allowed_commands=[],
        trace_id="trace-1",
        as_of_sim_time=0.0,
    )

    with pytest.raises(ValueError, match="explicit allow-list"):
        command_result(params)


def test_prepare_command_returns_a_typed_non_mutating_proposal() -> None:
    params = FashionCommandParams(
        workflow_id="WF-1",
        command_id="CMD-1",
        command_type="inventory.transfer",
        payload={"quantity": 20},
        allowed_commands=["inventory.transfer"],
        actor_ids=["INV-SOURCE", "INV-DEST"],
        event_ids=["evt-1"],
        trace_id="trace-1",
        as_of_sim_time=1.0,
    )

    result = json.loads(command_result(params).text_result_for_llm)

    assert result["command"] == {
        "command_id": "CMD-1",
        "trace_id": "trace-1",
        "issued_by": "fashion",
        "type": "inventory.transfer",
        "payload": {
            "quantity": 20,
            "workflow_id": "WF-1",
            "evidence_event_ids": ["evt-1"],
        },
    }
    assert result["source_mode"] == "simulated"
