from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from copilot.tools import ToolInvocation

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from api.shared.types import Workflow
from api.shared.vertical_loader import build_runtime
from verticals.electronics.agents import ELECTRONICS_AGENTS
from verticals.electronics.mcp_tools.common import RetailEvidence
from verticals.electronics.mcp_tools import retail
from verticals.electronics.process_profiles import ELECTRONICS_PROCESS_PROFILES

PACK_ROOT = Path(__file__).resolve().parents[3] / "verticals" / "electronics"

# Hero domestic high-value transfer world constants (see
# verticals/electronics/world.py, verticals/electronics/reference_cases.py and
# tests/api/electronics/test_launch_shock.py).
HERO_SKU = "SKU-APEX-X1-GRAPHITE-16"
HERO_SOURCE = "DC-UK-MID-01"
HERO_DESTINATION = "STORE-UK-LON-01"

EXPECTED_TOOLS = {
    "electronics_read_inventory",
    "electronics_prepare_inventory_transfer",
    "electronics_assess_promotion",
    "electronics_prepare_markdown_recommendation",
    "electronics_prepare_supplier_recovery",
    "electronics_prepare_fulfilment_resolution",
    "electronics_prepare_seller_suppression",
    "electronics_prepare_return_disposition",
}

_MISSING_DEFAULT = object()


def _workflow(workflow_type: str, *, transfer_candidate: dict | None = _MISSING_DEFAULT) -> Workflow:
    profile = ELECTRONICS_PROCESS_PROFILES[workflow_type]
    actor_ids = (
        [
            HERO_SKU,
            HERO_SOURCE,
            HERO_DESTINATION,
            f"STOCK-{HERO_SOURCE}-{HERO_SKU}",
            f"STOCK-{HERO_DESTINATION}-{HERO_SKU}",
        ]
        if workflow_type == "inventory-rebalancing"
        else [f"ACTOR-{profile.prefix.upper()}-001"]
    )
    retail_case: dict[str, object] = {
        "workflow_type": workflow_type,
        "actor_ids": actor_ids,
        "case": {
            "id": f"CASE-{profile.prefix.upper()}-001",
            "subject_ids": actor_ids[:3],
        },
    }
    if workflow_type == "inventory-rebalancing":
        if transfer_candidate is _MISSING_DEFAULT:
            retail_case["transfer_candidate"] = {
                "source_location_id": HERO_SOURCE,
                "destination_location_id": HERO_DESTINATION,
                "sku_id": HERO_SKU,
            }
        elif transfer_candidate is not None:
            retail_case["transfer_candidate"] = transfer_candidate
    return Workflow.model_construct(
        id=f"{profile.prefix}-evt-00000142",
        type=workflow_type,
        status="completed",
        current_phase="Verify Outcome",
        created_at=1.0,
        sla_due_at=2.0,
        jurisdiction="UK",
        agency="Electronics Retail",
        payload={
            "retail_case": retail_case,
            "decision": {
                "command": {
                    "type": profile.command_type,
                    "payload": {
                        "workflow_id": f"{profile.prefix}-evt-00000142",
                        "approval_reference": "HITL-MERCH-001",
                    },
                },
                "reasoning": "Evidence-backed Electronics decision.",
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
        data={"sku_id": HERO_SKU},
        actor_ids=[HERO_SKU],
        event_ids=["evt-00000142"],
        trace_id="trace-42",
        as_of_sim_time=42,
    )

    result = await retail.electronics_read_inventory.handler(
        ToolInvocation(
            session_id="electronics-test",
            tool_call_id="tool-1",
            tool_name="electronics_read_inventory",
            arguments=params.model_dump(),
        )
    )
    payload = json.loads(result.text_result_for_llm)

    assert payload["source_mode"] == "simulated"
    assert payload["actor_ids"] == [HERO_SKU]
    assert payload["event_ids"] == ["evt-00000142"]
    assert payload["trace_id"] == "trace-42"


def test_electronics_tool_registry_matches_declared_tool_names() -> None:
    assert set(retail.TOOL_BY_NAME) == retail.TOOL_NAMES


def test_tool_names_agree_across_agents_policies_and_skill_frontmatter() -> None:
    agent_tools = {
        tool for agent in ELECTRONICS_AGENTS.values() for tool in agent.allowed_tools
    }
    assert agent_tools == EXPECTED_TOOLS

    policy = yaml.safe_load(
        (PACK_ROOT / "policies" / "tools.yaml").read_text(encoding="utf-8")
    )
    policy_tools = {entry["id"] for entry in policy["tools"]}
    assert policy_tools == EXPECTED_TOOLS

    frontmatter_tools = set()
    for skill_file in (PACK_ROOT / "skills").glob("*/SKILL.md"):
        match = re.search(r"^allowed-tools:\s*(\S+)\s*$", skill_file.read_text(), re.M)
        assert match, f"{skill_file} is missing an allowed-tools frontmatter field"
        frontmatter_tools.add(match.group(1).strip())
    assert frontmatter_tools == EXPECTED_TOOLS


def test_hero_projection_keeps_world_workflow_and_stock_ids_connected(
    tmp_path,
) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "electronics"},
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
        HERO_SKU,
        HERO_SOURCE,
        HERO_DESTINATION,
        f"STOCK-{HERO_SOURCE}-{HERO_SKU}",
        f"STOCK-{HERO_DESTINATION}-{HERO_SKU}",
    ):
        assert actor_id in entities
    assert any(
        rel.rel == "HOSTED_ON"
        and rel.src_id == f"STOCK-{HERO_DESTINATION}-{HERO_SKU}"
        and rel.dst_id == HERO_DESTINATION
        for rel in relationships
    )
    assert any(
        rel.rel == "ASSET_AT_SITE"
        and rel.src_id == HERO_SKU
        and rel.dst_id == HERO_DESTINATION
        for rel in relationships
    )
    assert any(
        rel.rel == "WORKFLOW_IN_PERIOD"
        and rel.src_id == workflow.id
        for rel in relationships
    )
    assert decisions
    assert decisions[0].workflow_id == workflow.id
    assert HERO_SKU in decisions[0].decided_on


def test_every_workflow_projection_is_nonempty_and_keeps_workflow_id(
    tmp_path,
) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "electronics"},
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
        {"ZAVA_VERTICAL": "electronics"},
        data_root=tmp_path,
    ).pack
    workflow = _workflow("inventory-rebalancing")
    workflow.payload.pop("decisions")
    workflow.payload["decision"]["reasoning"] = {
        "summary": "Approved domestic high-value transfer.",
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


@pytest.mark.parametrize(
    "transfer_candidate",
    [None, {"source_location_id": HERO_SOURCE}],
)
def test_inventory_rebalancing_projection_fails_closed_without_transfer_candidate(
    tmp_path,
    transfer_candidate,
) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "electronics"},
        data_root=tmp_path,
    ).pack
    workflow = _workflow(
        "inventory-rebalancing",
        transfer_candidate=transfer_candidate,
    )

    with pytest.raises(ValueError, match="transfer_candidate"):
        list(pack.projections[workflow.type](workflow))


class _FakeGraph:
    def __init__(self) -> None:
        self.operations: list[EntityWrite] = []

    def upsert(self, operation: EntityWrite) -> None:
        self.operations.append(operation)


class _FakeState:
    def __init__(self) -> None:
        self.entities = _FakeGraph()


def test_lifecycle_bootstrap_writes_current_electronics_ids_with_no_stale_literals() -> None:
    from verticals.electronics.lifecycle import bootstrap

    state = _FakeState()
    bootstrap(state)

    written = {op.id: op for op in state.entities.operations}
    assert HERO_DESTINATION in written
    assert written[HERO_DESTINATION].attrs["identifier"] == "London Central"
    assert HERO_SOURCE in written
    assert written[HERO_SOURCE].attrs["identifier"] == "Midlands Fulfilment Hub"
    assert HERO_SKU in written

    serialised = json.dumps(
        [
            {"kind": op.kind, "id": op.id, "attrs": op.attrs}
            for op in state.entities.operations
        ]
    )
    for stale in ("Paris", "STORE-EU", "SKU-STYLE", "style-advisor"):
        assert stale not in serialised
