from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.server.routes import exceptions as exceptions_route
from api.server.services import pending_gates
from api.server.services.exception_factory import compose_hitl_exception
from api.server.services.governance.kernel import GovernanceKernel
from api.server.services.world_workflow_adapter import workflow_id_for
from api.server.state import app_state
from api.server.world.runtime import SimulationRuntime
from api.server.world.service import ActorWorldService
from api.shared.types import Workflow
from api.shared.vertical_loader import (
    active_runtime,
    build_runtime,
    discover_pack_modules,
    validate_pack,
)
from verticals.airline.domains import AIRLINE_DOMAINS
from verticals.airline.lifecycle import start
from verticals.airline.process_profiles import WORKFLOW_TYPE
from verticals.airline.worlds.active import resolve_active_airline_world


def test_completed_golden_pack_is_discovered_and_valid(tmp_path) -> None:
    assert discover_pack_modules()["airline"] == "verticals.airline.manifest"
    runtime = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path)
    validate_pack(runtime.pack)
    assert runtime.pack.display_name == "Synthetic Airline Operations"
    assert runtime.world_name == "airline"
    assert tuple(runtime.pack.domains) == ("integrated-hub-disruption-recovery",)
    assert runtime.pack.memory_workflow_types == ("integrated-hub-disruption-recovery",)


def test_golden_slice_mutates_real_world_and_preserves_identity(tmp_path) -> None:
    runtime = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path)
    world = runtime.pack.worlds["airline"].scales["demo"].build_scenario(SimulationRuntime(seed=42))
    source_event = world.activate_scenario("synthetic-hub-cascade")
    observation = world.build_observation(source_event.to_dict())
    command = world.command_for_option(
        option_id="SYN-OPTION-TAIL-CREW-STAND",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )
    result = world.apply_command(command)
    evaluation = world.recovery_evaluations["AIRHUB-0001"]
    assert observation["story_id"] == "SYN-STORY-HUB-001"
    assert observation["no_action_baseline"] == {
        "cancellations": 1,
        "departure_zero_recovered": 0,
        "departure_within_fifteen_recovered": 0,
        "protected_connection_cohorts": 0,
        "passengers_requiring_rerouting": 26,
    }
    assert result.type == "command.accepted"
    assert result.payload["workflow_id"] == "AIRHUB-0001"
    assert evaluation.workflow_id == "AIRHUB-0001"
    assert evaluation.cancellations_avoided >= 1
    assert evaluation.protected_connection_cohorts >= 1


@pytest.mark.asyncio
async def test_lifecycle_registers_resets_and_unregisters_real_world(
    tmp_path: Path,
) -> None:
    runtime = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path)
    service = ActorWorldService.for_runtime(
        runtime,
        seed=42,
        bus=SimpleNamespace(publish=lambda _event: None),
    )
    state = SimpleNamespace(world_service=service, runtime=runtime)

    stops = await start(state)
    first = service.scenario
    assert resolve_active_airline_world() is first

    service.reset(seed=43)
    second = service.scenario
    assert second is not first
    assert resolve_active_airline_world() is second

    for stop in reversed(stops):
        stop()
    with pytest.raises(RuntimeError, match="no active Airline world"):
        resolve_active_airline_world()


def test_browser_payload_identity_is_stable_across_world_records(
    tmp_path: Path,
) -> None:
    runtime = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path)
    world = runtime.pack.worlds["airline"].scales["demo"].build_scenario(SimulationRuntime(seed=42))
    source_event = world.activate_scenario("synthetic-hub-cascade")
    observation = world.build_observation(source_event.to_dict())
    sensor_event = next(
        event
        for event in world.runtime.journal
        if event.type == "sensor.tripped" and event.cause_event_id == source_event.event_id
    )
    trigger_result = world.run_reference_process(WORKFLOW_TYPE)
    command = world.command_for_option(
        option_id="SYN-OPTION-TAIL-CREW-STAND",
        workflow_id="AIRHUB-0001",
        decision_id="SYN-DECISION-001",
        persona="duty_operations_manager",
    )
    result = world.apply_command(command)
    snapshot = world.render_state()

    assert observation["story_id"] == "SYN-STORY-HUB-001"
    assert source_event.payload["workflow_id"] == "AIRHUB-0001"
    assert sensor_event.payload["workflow_id"] == "AIRHUB-0001"
    assert trigger_result["workflow_id"] == "AIRHUB-0001"
    assert (
        workflow_id_for(
            "ihdr",
            sensor_event.event_id,
            declared_workflow_id=sensor_event.payload["workflow_id"],
        )
        == "AIRHUB-0001"
    )
    assert command.type == "airline.commit_recovery_plan"
    assert result.payload["workflow_id"] == "AIRHUB-0001"
    assert {item["workflow_id"] for item in snapshot["recovery_commands"]} == {"AIRHUB-0001"}
    assert {item["workflow_id"] for item in snapshot["recovery_evaluations"]} == {"AIRHUB-0001"}


@pytest.mark.asyncio
async def test_browser_approval_preserves_airline_hitl_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = Workflow.model_construct(
        id="AIRHUB-0001",
        type=WORKFLOW_TYPE,
        status="awaiting_hitl",
        current_phase="Approve Recovery Plan",
        created_at=time.time(),
        sla_due_at=time.time() + 900,
        jurisdiction="Synthetic",
        agency="Synthetic Airline Operations",
        orchestration_instance_id="airline-instance-1",
        payload={
            "hitl_context": {
                "workflow_id": "AIRHUB-0001",
                "story_id": "SYN-STORY-HUB-001",
                "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
                "decision_id": "SYN-DECISION-001",
                "evidence_versions": {"SYN-SECTOR-OUT-001": 1},
                "persona": "duty_operations_manager",
            }
        },
    )
    app_state.store.upsert_workflow(workflow)
    pending_gates.record(
        workflow.id,
        phase=workflow.current_phase,
        external_event="duty_operations_manager_decision",
    )
    exception = compose_hitl_exception(
        app_state.store,
        workflow.id,
        "awaiting_approval",
    )
    raised: list[dict] = []

    async def capture_event(
        _instance_id: str,
        _event_name: str,
        payload: dict,
    ) -> bool:
        raised.append(payload)
        return True

    import api.server.services.durable_client as durable_client

    monkeypatch.setattr(
        durable_client,
        "raise_orchestration_event",
        capture_event,
    )
    monkeypatch.setattr(
        exceptions_route._registry,
        "DOMAINS",
        AIRLINE_DOMAINS,
    )
    try:
        assert await exceptions_route._resolve_one(
            exception.id,
            "approve",
            "world-operator",
        )
    finally:
        pending_gates.reset()
        app_state.store._workflows.pop(workflow.id, None)
        app_state.store._exceptions.pop(exception.id, None)

    assert raised == [
        {
            "decision": "approve",
            "resolved_by": "world-operator",
            "persona": "duty_operations_manager",
            "decision_id": "SYN-DECISION-001",
            "workflow_id": "AIRHUB-0001",
            "story_id": "SYN-STORY-HUB-001",
            "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
            "evidence_versions": {"SYN-SECTOR-OUT-001": 1},
        }
    ]


def test_real_governance_kernel_uses_current_airline_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZAVA_VERTICAL", "airline")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    try:
        governance = GovernanceKernel()
        authority = governance.check_authority(
            role="duty_operations_manager",
            action="airline.commit_recovery_plan",
            category="synthetic-operational-recovery",
            value=75_000.0,
        )
    finally:
        active_runtime.cache_clear()

    assert authority.allowed is True
    assert authority.governing_rule_id == ("AUTH-duty_operations_manager-airline.commit_recovery_plan")
