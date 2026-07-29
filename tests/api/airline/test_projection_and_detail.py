from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from api.server.services.governance.manifest import load_tools_yaml
from api.server.world.runtime import SimulationRuntime
from api.shared.types import Workflow
from api.shared.vertical_loader import build_runtime
from verticals.airline.constraints import admit_recovery_options
from verticals.airline.detail import workflow_detail
from verticals.airline.process_profiles import WORKFLOW_TYPE


PACK_ROOT = Path(__file__).resolve().parents[3] / "verticals" / "airline"
DESIGN_COMMIT = "b50713ed2b6324ac917402a41fc6e9c08c5c5262"


def _option_dict(result: Any) -> dict[str, Any]:
    return {
        "option_id": result.option.option_id,
        "impact": result.option.impact,
        "value_gbp": result.option.value_gbp,
        "actions": [action.to_dict() for action in result.option.actions],
        "evidence_versions": dict(result.option.evidence_versions),
        "feasible": result.feasible,
        "admitted": result.feasible,
        "reasons": list(result.reasons),
    }


def _completed_workflow(tmp_path: Path) -> tuple[Workflow, Any]:
    runtime = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path)
    world = runtime.pack.worlds["airline"].scales["demo"].build_scenario(SimulationRuntime(seed=42))
    source_event = world.activate_scenario("synthetic-hub-cascade")
    observation = world.build_observation(source_event.to_dict())
    observation["actor_ids"] = list(observation["evidence_versions"])
    observation["event_ids"] = list(observation["evidence_event_ids"])
    results = admit_recovery_options(observation)
    admitted = [_option_dict(result) for result in results if result.feasible]
    rejected = [_option_dict(result) for result in results if not result.feasible]
    command = world.command_for_option(
        option_id="SYN-OPTION-TAIL-CREW-STAND",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )
    gateway_event = world.apply_command(command)
    selected = next(option for option in admitted if option["option_id"] == "SYN-OPTION-TAIL-CREW-STAND")
    authority = {
        "allowed": True,
        "reason": "Duty Operations Manager is within the synthetic authority band.",
        "governing_rule_id": ("AUTH-duty_operations_manager-airline.commit_recovery_plan"),
    }
    evidence = {
        "status": "decision_ready",
        "workflow_evidence": {
            "workflow_id": "AIRHUB-0001",
            "story_id": "SYN-STORY-HUB-001",
            "source_mode": "simulated",
            "actor_ids": observation["actor_ids"],
            "event_ids": observation["event_ids"],
            "evidence_versions": observation["evidence_versions"],
            "observation": observation,
        },
        "approval": {
            "decision": "approve",
            "persona": "duty_operations_manager",
            "decision_id": "SYN-DECISION-001",
            "selected_option_id": selected["option_id"],
            "evidence_versions": observation["evidence_versions"],
            "workflow_id": "AIRHUB-0001",
            "story_id": "SYN-STORY-HUB-001",
            "rationale": "Protect the hub bank with the admitted bounded plan.",
        },
        "command": command.to_dict(),
        "gateway_event": gateway_event.to_dict(),
        "evaluation": {
            "status": "pending_world_event_pipeline",
            "success_event": "airline.recovery.applied",
        },
        "reasoning": {
            "impact": {
                "phase": "Assess Network Impact",
                "impact_summary": "Inbound delay constrains tail, crew, stand, slot, and connections.",
                "actor_ids": observation["actor_ids"],
                "event_ids": observation["event_ids"],
            },
            "admission": {
                "admitted_options": admitted,
                "rejected_options": rejected,
            },
            "ranking": {
                "phase": "Synthesize Recovery Options",
                "ranked_option_ids": [
                    "SYN-OPTION-TAIL-CREW-STAND",
                    "SYN-OPTION-CANCEL",
                ],
                "reasoning": "The bounded tail, crew, and stand plan protects service.",
            },
            "authority": authority,
        },
        "hitl_context": {
            "workflow_id": "AIRHUB-0001",
            "story_id": "SYN-STORY-HUB-001",
            "persona": "duty_operations_manager",
            "decision_id": "SYN-DECISION-001",
            "selected_option_id": selected["option_id"],
            "selected_option": selected,
            "admitted_options": admitted,
            "evidence_versions": observation["evidence_versions"],
            "authority": authority,
        },
    }
    workflow = Workflow.model_construct(
        id="AIRHUB-0001",
        type=WORKFLOW_TYPE,
        status="completed",
        current_phase="Verify Recovery Outcome",
        created_at=1.0,
        sla_due_at=2.0,
        jurisdiction="Synthetic",
        agency="Synthetic Airline Operations",
        payload={"observation": observation, "evidence": evidence},
        orchestration_instance_id="airline-instance-1",
    )
    return workflow, world


def test_projection_writes_complete_canonical_recovery_graph(
    tmp_path: Path,
) -> None:
    pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
    workflow, _world = _completed_workflow(tmp_path)

    operations = list(pack.projections[WORKFLOW_TYPE](workflow))

    assert any(
        isinstance(item, EntityWrite) and item.kind == "Workflow" and item.id == workflow.id
        for item in operations
    )
    assert {
        workflow.id,
        "SYN-STORY-HUB-001",
        "SYN-DISRUPTION-HUB-001",
        "SYN-TAIL-001",
        "SYN-SECTOR-IN-001",
        "SYN-SECTOR-OUT-001",
        "SYN-SECTOR-OUT-002",
        "SYN-CREW-DUTY-01",
        "SYN-SLOT-05",
        "SYN-STAND-01",
        "SYN-COHORT-001",
        "SYN-DECISION-001",
        "SYN-EVAL-AIRHUB-0001",
    } <= {item.id for item in operations if isinstance(item, EntityWrite)}
    assert any(
        isinstance(item, EntityWrite)
        and item.kind == "Decision"
        and item.attrs.get("phase") == "Commit Recovery Actions"
        and item.attrs.get("workflow_id") == workflow.id
        for item in operations
    )
    assert any(
        isinstance(item, DecisionWrite)
        and item.workflow_id == workflow.id
        and item.persona_role == "duty_operations_manager"
        for item in operations
    )

    relationships = [item for item in operations if isinstance(item, RelWrite)]
    assert any(
        item.src_id == workflow.id and item.rel == "TRIGGERED_BY" and item.dst_id == "SYN-STORY-HUB-001"
        for item in relationships
    )
    assert any(
        item.src_id == "SYN-SECTOR-OUT-001" and item.rel == "RELATED_ASSET" and item.dst_id == "SYN-TAIL-005"
        for item in relationships
    )
    assert any(
        item.src_id == "SYN-COHORT-001"
        and item.rel == "RELATED_ASSET"
        and item.dst_id == "SYN-SECTOR-OUT-002"
        for item in relationships
    )
    assert any(item.src_id == "SYN-DECISION-001" and item.rel == "ISSUED_COMMAND" for item in relationships)
    assert any(item.rel == "EVALUATED_BY" and item.dst_id == "SYN-EVAL-AIRHUB-0001" for item in relationships)


def test_detail_exposes_only_real_golden_slice_evidence(tmp_path: Path) -> None:
    workflow, world = _completed_workflow(tmp_path)
    state = SimpleNamespace(
        world_service=SimpleNamespace(scenario=world),
    )

    detail = workflow_detail(workflow, state)

    assert detail is not None
    assert detail["workflow_id"] == "AIRHUB-0001"
    assert detail["story"] == {
        "story_id": "SYN-STORY-HUB-001",
        "scenario_id": "synthetic-hub-cascade",
        "source_mode": "simulated",
        "source_event_id": detail["story"]["source_event_id"],
        "sensor_event_id": detail["story"]["sensor_event_id"],
    }
    assert detail["baseline"]["outbound_sector_id"] == "SYN-SECTOR-OUT-001"
    assert detail["chosen_admitted_option"]["option_id"] == ("SYN-OPTION-TAIL-CREW-STAND")
    assert detail["chosen_admitted_option"]["admitted"] is True
    assert detail["rejected_options"] == [
        {
            **detail["rejected_options"][0],
            "option_id": "SYN-OPTION-RETIME-ONLY",
        }
    ]
    assert {"crew", "slot"} <= set(detail["rejected_options"][0]["reasons"])
    assert detail["governance"]["persona"] == "duty_operations_manager"
    assert detail["governance"]["decision_id"] == "SYN-DECISION-001"
    assert detail["governance"]["authority"]["allowed"] is True
    assert detail["mutations"]["command_type"] == ("airline.commit_recovery_plan")
    assert {
        "SYN-SECTOR-OUT-001",
        "SYN-TAIL-005",
        "SYN-DUTY-006",
        "SYN-STAND-05",
    } <= set(detail["mutations"]["affected_actor_ids"])
    assert detail["evaluation"]["workflow_id"] == "AIRHUB-0001"
    assert detail["evaluation"]["cancellations_avoided"] >= 1
    assert detail["evaluation"]["protected_connection_cohorts"] >= 1
    assert {item["kind"] for item in detail["timeline"]} == {
        "deterministic",
        "agent",
        "hitl",
    }


def test_detail_is_truthful_while_waiting_for_hitl(tmp_path: Path) -> None:
    workflow, _world = _completed_workflow(tmp_path)
    context = workflow.payload["evidence"]["hitl_context"]
    workflow.status = "awaiting_hitl"
    workflow.payload = {
        "observation": workflow.payload["observation"],
        "hitl_context": context,
    }

    detail = workflow_detail(workflow, SimpleNamespace(world_service=None))

    assert detail is not None
    assert detail["chosen_admitted_option"]["option_id"] == ("SYN-OPTION-TAIL-CREW-STAND")
    assert detail["governance"]["status"] == "pending"
    assert detail["governance"]["decision_id"] == "SYN-DECISION-001"
    assert detail["mutations"] is None
    assert detail["evaluation"] is None


def test_tool_policy_allows_only_the_two_matching_airline_tools() -> None:
    tools = load_tools_yaml(str(PACK_ROOT / "policies" / "tools.yaml"))

    assert set(tools) == {
        "airline_read_disruption_evidence",
        "airline_rank_feasible_recovery_options",
    }
    assert {tool.scope_function for tool in tools.values()} == {"operations-control"}
    assert all(tool.reversible for tool in tools.values())
    assert all(not tool.requires_authority for tool in tools.values())


def test_generation_manifest_is_a_complete_bespoke_ownership_ledger() -> None:
    manifest = json.loads((PACK_ROOT / "generation-manifest.json").read_text(encoding="utf-8"))
    records = manifest["records"]
    recorded_paths = {record["path"] for record in records}
    actual_paths = {
        str(path.relative_to(PACK_ROOT.parents[1]))
        for path in PACK_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith((".pyc", ".pyo"))
    }

    assert manifest["schema_version"] == 1
    assert manifest["vertical"] == "airline"
    assert recorded_paths == actual_paths
    assert all(record["ownership"] == "bespoke" for record in records)
    assert all(record["source"] == DESIGN_COMMIT for record in records)
