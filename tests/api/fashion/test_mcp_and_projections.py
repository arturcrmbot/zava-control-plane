from __future__ import annotations

import json

import pytest
from copilot.tools import ToolInvocation

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from api.shared.types import Workflow
from api.shared.vertical_loader import build_runtime
from verticals.fashion.mcp_tools.common import RetailEvidence
from verticals.fashion.mcp_tools import retail
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


EXPECTED_TOOLS = {
    "fashion_read_inventory",
    "fashion_prepare_inventory_transfer",
    "fashion_assess_promotion",
    "fashion_prepare_markdown_recommendation",
    "fashion_prepare_supplier_recovery",
    "fashion_prepare_fulfilment_resolution",
    "fashion_prepare_seller_suppression",
    "fashion_prepare_return_disposition",
}


def _workflow(workflow_type: str) -> Workflow:
    profile = FASHION_PROCESS_PROFILES[workflow_type]
    actor_ids = (
        [
            "SKU-STYLE-01-BLK-M",
            "STORE-EU-PAR-01",
            "STORE-UK-LON-01",
            "STOCK-STORE-EU-PAR-01-SKU-STYLE-01-BLK-M",
            "STOCK-STORE-UK-LON-01-SKU-STYLE-01-BLK-M",
        ]
        if workflow_type == "inventory-rebalancing"
        else [f"ACTOR-{profile.prefix.upper()}-001"]
    )
    return Workflow.model_construct(
        id=f"{profile.prefix}-evt-00000142",
        type=workflow_type,
        status="completed",
        current_phase="Verify Outcome",
        created_at=1.0,
        sla_due_at=2.0,
        jurisdiction="UK/EU",
        agency="Fashion Retail",
        payload={
            "retail_case": {
                "workflow_type": workflow_type,
                "actor_ids": actor_ids,
                "case": {
                    "id": f"CASE-{profile.prefix.upper()}-001",
                    "subject_ids": actor_ids[:3],
                },
                "transfer_candidate": {
                    "source_location_id": "STORE-EU-PAR-01",
                    "destination_location_id": "STORE-UK-LON-01",
                    "sku_id": "SKU-STYLE-01-BLK-M",
                },
            },
            "decision": {
                "command": {
                    "type": profile.command_type,
                    "payload": {
                        "workflow_id": f"{profile.prefix}-evt-00000142",
                        "approval_reference": "HITL-MERCH-001",
                    },
                },
                "reasoning": "Evidence-backed Fashion decision.",
            },
            "outcome": {
                "status": "resolved",
                "evidence_event_type": profile.success_event,
            },
            "decisions": [
                {
                    "phase": (
                        "Approve Exception"
                        if workflow_type == "inventory-rebalancing"
                        else "Approval"
                    ),
                    "verdict": "approve",
                    "reason": "Within delegated authority.",
                    "decided_at": "2026-07-22T14:00:00+00:00",
                    "persona_role": profile.hitl_persona,
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_mcp_pack_exposes_exact_tools_with_simulated_provenance() -> None:
    assert retail.TOOL_NAMES == EXPECTED_TOOLS
    params = RetailEvidence(
        data={"sku_id": "SKU-STYLE-01-BLK-M"},
        actor_ids=["SKU-STYLE-01-BLK-M"],
        event_ids=["evt-00000142"],
        trace_id="trace-42",
        as_of_sim_time=42,
    )

    result = await retail.fashion_read_inventory.handler(
        ToolInvocation(
            session_id="fashion-test",
            tool_call_id="tool-1",
            tool_name="fashion_read_inventory",
            arguments=params.model_dump(),
        )
    )
    payload = json.loads(result.text_result_for_llm)

    assert payload["source_mode"] == "simulated"
    assert payload["actor_ids"] == ["SKU-STYLE-01-BLK-M"]
    assert payload["event_ids"] == ["evt-00000142"]
    assert payload["trace_id"] == "trace-42"


def test_hero_projection_keeps_world_workflow_and_stock_ids_connected(
    tmp_path,
) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    ).pack
    workflow = _workflow("inventory-rebalancing")

    operations = list(pack.projections[workflow.type](workflow))
    entities = {
        operation.id: operation
        for operation in operations
        if isinstance(operation, EntityWrite)
    }
    relationships = [
        operation for operation in operations if isinstance(operation, RelWrite)
    ]
    decisions = [
        operation for operation in operations if isinstance(operation, DecisionWrite)
    ]

    assert workflow.id in entities
    for actor_id in (
        "SKU-STYLE-01-BLK-M",
        "STORE-EU-PAR-01",
        "STORE-UK-LON-01",
        "STOCK-STORE-EU-PAR-01-SKU-STYLE-01-BLK-M",
        "STOCK-STORE-UK-LON-01-SKU-STYLE-01-BLK-M",
    ):
        assert actor_id in entities
    assert any(
        rel.rel == "HOSTED_ON"
        and rel.src_id == "STOCK-STORE-UK-LON-01-SKU-STYLE-01-BLK-M"
        and rel.dst_id == "STORE-UK-LON-01"
        for rel in relationships
    )
    assert any(
        rel.rel == "ASSET_AT_SITE"
        and rel.src_id == "SKU-STYLE-01-BLK-M"
        and rel.dst_id == "STORE-UK-LON-01"
        for rel in relationships
    )
    assert any(
        rel.rel == "WORKFLOW_IN_PERIOD"
        and rel.src_id == workflow.id
        for rel in relationships
    )
    assert decisions
    assert decisions[0].workflow_id == workflow.id
    assert "SKU-STYLE-01-BLK-M" in decisions[0].decided_on


def test_every_workflow_projection_is_nonempty_and_keeps_workflow_id(
    tmp_path,
) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    ).pack

    for workflow_type, projection in pack.projections.items():
        workflow = _workflow(workflow_type)
        operations = list(projection(workflow))
        assert operations
        assert any(
            isinstance(operation, EntityWrite)
            and operation.kind == "Workflow"
            and operation.id == workflow.id
            for operation in operations
        )


def test_projection_materialises_live_durable_authority_decision(tmp_path) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    ).pack
    workflow = _workflow("inventory-rebalancing")
    workflow.payload.pop("decisions")
    workflow.payload["decision"]["reasoning"] = {
        "summary": "Approved cross-border transfer.",
        "authority": {
            "persona": "merchandising_director",
            "decision": "approve",
            "decision_id": "HITL-MERCH-001",
        },
    }

    decisions = [
        operation
        for operation in pack.projections[workflow.type](workflow)
        if isinstance(operation, DecisionWrite)
    ]

    assert len(decisions) == 1
    assert decisions[0].persona_role == "merchandising_director"
    assert decisions[0].verdict == "approve"
    assert decisions[0].attributes["decision_id"] == "HITL-MERCH-001"
