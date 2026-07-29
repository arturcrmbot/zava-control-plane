from __future__ import annotations

from collections import Counter
from importlib import import_module

from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime


STORY_ID = "electronics-launch-shock-42"
HERO_SKU = "SKU-APEX-X1-GRAPHITE-16"
SOURCE = "DC-UK-MID-01"
DESTINATION = "STORE-UK-LON-01"


def _scenario(seed: int = 42):
    module = import_module("verticals.electronics.world")
    runtime = SimulationRuntime(seed)
    scenario = module.ElectronicsScenario(runtime)
    scenario.install()
    return runtime, scenario


def _inventory_command(
    scenario,
    *,
    command_id: str,
    workflow_id: str,
    approval_reference: str | None,
) -> SimulationCommand:
    source = scenario.inventory[(SOURCE, HERO_SKU)]
    destination = scenario.inventory[(DESTINATION, HERO_SKU)]
    return SimulationCommand(
        command_id=command_id,
        trace_id=STORY_ID,
        issued_by="merchandising-planning",
        type="inventory.transfer",
        payload={
            "workflow_id": workflow_id,
            "source_location_id": SOURCE,
            "destination_location_id": DESTINATION,
            "sku_id": HERO_SKU,
            "quantity": 24,
            "ownership": "owned",
            "expected_source_version": source.version,
            "expected_destination_version": destination.version,
            "policy_decision": "approval_required",
            "approval_reference": approval_reference,
            "reason_code": "LAUNCH_STOCK_IMBALANCE",
            "evidence_digest": "sha256:deterministic-electronics-evidence",
            "story_id": STORY_ID,
        },
    )


def test_launch_shock_has_visible_story_identity_and_detection_event() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)

    story_events = [
        event
        for event in runtime.canonical_journal()
        if event["type"] == "retail.launch-shock.detected"
    ]
    assert len(story_events) == 1
    assert story_events[0]["trace_id"] == STORY_ID
    assert story_events[0]["payload"]["story_id"] == STORY_ID
    assert story_events[0]["cause_event_id"] is not None

    story = scenario.render_state()["story"]
    assert story["id"] == STORY_ID
    assert story["trace_id"] == STORY_ID
    assert story["type"] == "launch-shock"
    assert story["title"] == "The flagship gaming launch"
    assert story["status"] == "running"
    assert [stage["display_name"] for stage in story["stages"]] == [
        "Launch Demand Response",
        "Inventory Rebalancing",
        "Launch Promotion Readiness",
        "Supplier Allocation Recovery",
        "Marketplace Seller Exception",
        "Omnichannel Fulfilment Recovery",
        "Launch Margin Governance",
        "Returns & Repair Disposition",
    ]
    demand = story["stages"][0]
    assert demand["function"] == "merchandising-planning"
    assert demand["command_type"] == "allocation.adjust"
    assert demand["success_event"] == "allocation.adjusted"
    assert demand["skills"] == ["inventory-imbalance-analysis"]
    assert [phase["name"] for phase in demand["phases"]] == [
        "Detect Regional Demand",
        "Assess Stock Exposure",
        "Approve Allocation Exception",
        "Adjust Allocation",
        "Verify Availability",
    ]
    assert demand["hitl_persona"] == "inventory_allocation_manager"


def test_threshold_starts_the_shock_with_exactly_two_root_sensors() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)

    sensors = [
        event
        for event in runtime.canonical_journal()
        if event["type"] == "sensor.tripped"
        and event["payload"].get("story_id") == STORY_ID
    ]
    assert Counter(event["payload"]["workflow_type"] for event in sensors) == {
        "demand-spike-response": 1,
        "inventory-rebalancing": 1,
    }
    inventory_sensor = next(
        event
        for event in sensors
        if event["payload"]["workflow_type"] == "inventory-rebalancing"
    )
    assert inventory_sensor["actor_id"] == "sensor:inventory_imbalance"
    assert inventory_sensor["payload"]["source_location_id"] == SOURCE
    assert inventory_sensor["payload"]["destination_location_id"] == DESTINATION


def test_eight_stage_dependency_order_unlocks_and_fires_each_sensor_once() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)

    def story_sensor(workflow_type: str) -> dict:
        return next(
            event.to_dict()
            for event in runtime.journal
            if event.type == "sensor.tripped"
            and event.payload.get("story_id") == STORY_ID
            and event.payload["workflow_type"] == workflow_type
        )

    def complete_reference(workflow_type: str) -> None:
        sensor = story_sensor(workflow_type)
        workflow_id = f"story-{workflow_type}"
        scenario.bind_story_workflow(sensor, workflow_id)
        command = scenario.command_for_reference_process(
            workflow_type,
            trace_id=STORY_ID,
            workflow_id=workflow_id,
            approval_decision="approve",
        )
        command = SimulationCommand(
            command_id=command.command_id,
            trace_id=command.trace_id,
            issued_by=command.issued_by,
            type=command.type,
            payload={**command.payload, "story_id": STORY_ID},
        )
        assert scenario.apply_command(command).type == "command.accepted"

    # Root stages unlock together; only after demand-spike-response and
    # inventory-rebalancing complete do their dependants become triggerable.
    complete_reference("demand-spike-response")
    inventory_sensor = story_sensor("inventory-rebalancing")
    inventory_workflow_id = "story-inventory-rebalancing"
    scenario.bind_story_workflow(inventory_sensor, inventory_workflow_id)
    assert scenario.apply_command(
        _inventory_command(
            scenario,
            command_id="CMD-STORY-REBALANCE",
            workflow_id=inventory_workflow_id,
            approval_reference="HITL-MERCH-001",
        )
    ).type == "command.accepted"

    for workflow_type in (
        "promotion-readiness",
        "supplier-delay-recovery",
        "marketplace-seller-exception",
        "fulfilment-exception-resolution",
        "markdown-governance",
        "returns-disposition",
    ):
        complete_reference(workflow_type)

    story_sensors = [
        event
        for event in runtime.journal
        if event.type == "sensor.tripped" and event.payload.get("story_id") == STORY_ID
    ]
    assert Counter(event.payload["workflow_type"] for event in story_sensors) == {
        "demand-spike-response": 1,
        "inventory-rebalancing": 1,
        "promotion-readiness": 1,
        "supplier-delay-recovery": 1,
        "marketplace-seller-exception": 1,
        "fulfilment-exception-resolution": 1,
        "markdown-governance": 1,
        "returns-disposition": 1,
    }
    story = scenario.trading_shock.view()
    assert story["status"] == "completed"
    assert set(story["kpis"]) == {
        "availability_pct",
        "destination_available_units",
        "projected_lost_sales_gbp",
        "process_completion_pct",
        "markdown_exposure_gbp",
        "recovery_value_gbp",
    }
    assert story["kpis"]["destination_available_units"] == {
        "before": 8,
        "after": 32,
    }
    assert story["kpis"]["process_completion_pct"] == {
        "before": 0.0,
        "after": 100.0,
    }
    assert (
        story["kpis"]["projected_lost_sales_gbp"]["after"]
        < story["kpis"]["projected_lost_sales_gbp"]["before"]
    )
    assert (
        story["kpis"]["recovery_value_gbp"]["after"]
        > story["kpis"]["recovery_value_gbp"]["before"]
    )


def test_story_completes_only_after_a_real_command_not_just_the_sensor() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)

    sensor = next(
        event.to_dict()
        for event in runtime.journal
        if event.type == "sensor.tripped"
        and event.payload.get("story_id") == STORY_ID
        and event.payload["workflow_type"] == "inventory-rebalancing"
    )
    workflow_id = "story-inventory"
    scenario.bind_story_workflow(sensor, workflow_id)
    assert scenario.trading_shock.stage("inventory-rebalancing").status == "active"

    source = scenario.inventory[(SOURCE, HERO_SKU)]
    destination = scenario.inventory[(DESTINATION, HERO_SKU)]
    source_before, destination_before = source.on_hand, destination.on_hand

    command = _inventory_command(
        scenario,
        command_id="CMD-STORY-SUCCESS",
        workflow_id=workflow_id,
        approval_reference="HITL-MERCH-001",
    )
    assert scenario.apply_command(command).type == "command.accepted"
    assert source.on_hand == source_before - 24
    assert destination.on_hand == destination_before + 24
    assert scenario.trading_shock.stage("inventory-rebalancing").status == "completed"


def test_rejected_story_command_fails_its_stage_without_unlocking_dependants() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)

    sensor = next(
        event.to_dict()
        for event in runtime.journal
        if event.type == "sensor.tripped"
        and event.payload.get("story_id") == STORY_ID
        and event.payload["workflow_type"] == "inventory-rebalancing"
    )
    workflow_id = "story-rejected-inventory"
    scenario.bind_story_workflow(sensor, workflow_id)

    command = _inventory_command(
        scenario,
        command_id="CMD-STORY-REJECTED",
        workflow_id=workflow_id,
        approval_reference=None,
    )

    assert scenario.apply_command(command).type == "command.rejected"
    assert scenario.trading_shock.stage("inventory-rebalancing").status == "failed"
    assert scenario.trading_shock.ready_to_trigger() == ()
    scenario.fail_story_workflow(workflow_id, "bridge rejection confirmation")
    assert scenario.trading_shock.stage("inventory-rebalancing").status == "failed"
