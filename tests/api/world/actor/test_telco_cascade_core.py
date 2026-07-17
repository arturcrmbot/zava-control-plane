from __future__ import annotations

from api.functions.activities.telco_cascade import telco_cascade_decision
from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from verticals.telco.world import NetworkConfig, NetworkScenario


def _scenario(seed: int = 41) -> NetworkScenario:
    runtime = SimulationRuntime(seed)
    scenario = NetworkScenario(
        runtime,
        NetworkConfig(
            site_count=12,
            subscriber_count=200,
            session_count=240,
            site_capacity_mbps=600.0,
            simulation_minutes=30.0,
        ),
    )
    scenario.install()
    return scenario


def _command(
    command_id: str,
    command_type: str,
    payload: dict,
    *,
    trace_id: str,
) -> SimulationCommand:
    return SimulationCommand(
        command_id=command_id,
        trace_id=trace_id,
        issued_by="test-responder",
        type=command_type,
        payload=payload,
    )


def _events(scenario: NetworkScenario, event_type: str):
    return [event for event in scenario.runtime.journal if event.type == event_type]


def _apply_decision(
    scenario: NetworkScenario,
    workflow_type: str,
    sensor,
) -> tuple[dict, SimulationCommand]:
    observation = scenario.build_observation(
        sensor.to_dict(),
        now=scenario.runtime.now,
    )
    decision = telco_cascade_decision(
        {
            "agent_mode": "deterministic",
            "workflow_id": f"WF-{workflow_type}",
            "trace_id": sensor.trace_id,
            "type": workflow_type,
            "observation": observation,
        }
    )
    command_data = decision["command"]
    if decision["requires_approval"]:
        command_data["payload"]["approval_decision"] = "approve"
    command = SimulationCommand(**command_data)
    scenario.apply_command(command)
    return decision, command


def test_storm_maintenance_and_field_repair_form_one_causal_story():
    scenario = _scenario()
    scenario.inject_weather_risk("west", 2.0, 10.0)
    outage_sensor = _events(scenario, "sensor.tripped")[-1]
    outage_decision, _ = _apply_decision(
        scenario,
        "outage-risk-management",
        outage_sensor,
    )
    assert outage_decision["requires_approval"] is True

    scenario.runtime.run_until(1.0)
    maintenance_sensor = next(
        event
        for event in _events(scenario, "sensor.tripped")
        if event.actor_id == "sensor:asset_failure_risk"
    )
    _apply_decision(
        scenario,
        "predictive-site-maintenance",
        maintenance_sensor,
    )
    field_sensor = _events(scenario, "sensor.tripped")[-1]
    field_decision, _ = _apply_decision(
        scenario,
        "field-repair-dispatch",
        field_sensor,
    )

    assert field_decision["requires_approval"] is True
    assert _events(scenario, "resources.prestaged")
    assert _events(scenario, "work_order.created")
    assert _events(scenario, "asset.repaired") or _events(
        scenario,
        "asset.replaced",
    )
    assert len(
        {
            outage_sensor.trace_id,
            maintenance_sensor.trace_id,
            field_sensor.trace_id,
        }
    ) == 3
    assert maintenance_sensor.payload["parent_trace_id"] == outage_sensor.trace_id
    assert field_sensor.payload["parent_trace_id"] == maintenance_sensor.trace_id


def test_weather_injection_opens_its_own_outage_risk_trace():
    scenario = _scenario()

    weather_id = scenario.inject_weather_risk("west", 1.5, 10.0)

    injected = _events(scenario, "weather.risk_injected")[-1]
    sensor = _events(scenario, "sensor.tripped")[-1]
    assert sensor.actor_id == "sensor:outage_risk"
    assert sensor.target_id == "region:west"
    assert sensor.cause_event_id == injected.event_id
    assert sensor.trace_id != injected.trace_id
    assert sensor.payload["weather_event_id"] == weather_id
    assert sensor.payload["parent_trace_id"] == injected.trace_id


def test_weather_risk_promotes_one_asset_into_a_maintenance_trace():
    scenario = _scenario()
    scenario.inject_weather_risk("west", 2.0, 10.0)

    scenario.runtime.run_until(1.0)

    sensors = [
        event
        for event in _events(scenario, "sensor.tripped")
        if event.actor_id == "sensor:asset_failure_risk"
    ]
    assert len(sensors) == 1
    sensor = sensors[0]
    asset = scenario.assets[sensor.target_id]
    assert scenario.sites[asset.site_id].region == "west"
    assert asset.risk_band in {"elevated", "high", "critical"}
    assert sensor.payload["parent_trace_id"].startswith("outage-risk-")
    assert sensor.trace_id != sensor.payload["parent_trace_id"]


def test_asset_failure_alert_remains_actionable_after_weather_expires():
    scenario = _scenario()
    scenario.inject_weather_risk("west", 2.0, 2.0)
    scenario.runtime.run_until(1.0)
    sensor = next(
        event
        for event in _events(scenario, "sensor.tripped")
        if event.actor_id == "sensor:asset_failure_risk"
    )
    asset = scenario.assets[sensor.target_id]

    scenario.runtime.run_until(3.0)
    accepted = scenario.apply_command(
        _command(
            "cmd-maintenance-after-weather",
            "create_maintenance_work_order",
            {"asset_id": asset.id, "kind": "repair", "priority": 2},
            trace_id=sensor.trace_id,
        )
    )

    assert accepted.type == "command.accepted"
    assert scenario.work_orders["WO-00001"].asset_id == asset.id


def test_prestage_command_reserves_real_available_technicians():
    scenario = _scenario()
    command = _command(
        "cmd-prestage-1",
        "prestage_field_resources",
        {
            "region": "west",
            "technician_ids": ["TECH-WEST-01"],
            "spare_part_kinds": ["power"],
        },
        trace_id="trace-outage-1",
    )

    accepted = scenario.apply_command(command)

    assert accepted.type == "command.accepted"
    assert scenario.technicians["TECH-WEST-01"].status == "prestaged"
    prestaged = _events(scenario, "resources.prestaged")[-1]
    assert prestaged.cause_event_id == accepted.event_id
    assert prestaged.trace_id == command.trace_id
    assert prestaged.payload["technician_ids"] == ["TECH-WEST-01"]


def test_exceptional_prestage_spend_requires_delivery_approval():
    scenario = _scenario()
    payload = {
        "region": "north",
        "technician_ids": [
            "TECH-NORTH-01",
            "TECH-NORTH-02",
            "TECH-NORTH-03",
            "TECH-NORTH-04",
        ],
        "spare_part_kinds": ["power", "cooling"],
        "estimated_cost_gbp": 11_000.0,
    }

    rejected = scenario.apply_command(
        _command(
            "cmd-prestage-expensive-denied",
            "prestage_field_resources",
            payload,
            trace_id="trace-outage-expensive-denied",
        )
    )
    assert rejected.type == "command.rejected"

    accepted = scenario.apply_command(
        _command(
            "cmd-prestage-expensive-approved",
            "prestage_field_resources",
            {**payload, "approval_decision": "approve"},
            trace_id="trace-outage-expensive-approved",
        )
    )
    assert accepted.type == "command.accepted"


def test_maintenance_command_creates_work_order_and_field_repair_trace():
    scenario = _scenario()
    asset = scenario.assets["AST-SITE-04-radio-unit"]
    asset.health = 0.1
    scenario._derive_asset_metrics(asset)
    command = _command(
        "cmd-maintenance-1",
        "create_maintenance_work_order",
        {"asset_id": asset.id, "kind": "repair", "priority": 1},
        trace_id="trace-maintenance-1",
    )

    accepted = scenario.apply_command(command)

    assert accepted.type == "command.accepted"
    work_order = scenario.work_orders["WO-00001"]
    assert work_order.asset_id == asset.id
    assert work_order.status == "open"
    assert asset.status == "degraded"
    created = _events(scenario, "work_order.created")[-1]
    sensor = _events(scenario, "sensor.tripped")[-1]
    assert sensor.actor_id == "sensor:work_order_ready"
    assert sensor.target_id == work_order.id
    assert sensor.cause_event_id == created.event_id
    assert sensor.trace_id != command.trace_id
    assert sensor.payload["parent_trace_id"] == command.trace_id


def test_asset_replacement_requires_delivery_approval():
    scenario = _scenario()
    asset = scenario.assets["AST-SITE-04-radio-unit"]
    asset.health = 0.1
    scenario._derive_asset_metrics(asset)
    payload = {"asset_id": asset.id, "kind": "replace", "priority": 1}

    rejected = scenario.apply_command(
        _command(
            "cmd-replace-denied",
            "create_maintenance_work_order",
            payload,
            trace_id="trace-replace-denied",
        )
    )
    assert rejected.type == "command.rejected"

    accepted = scenario.apply_command(
        _command(
            "cmd-replace-approved",
            "create_maintenance_work_order",
            {**payload, "approval_decision": "approve"},
            trace_id="trace-replace-approved",
        )
    )
    assert accepted.type == "command.accepted"


def test_field_dispatch_consumes_stock_and_repairs_the_asset():
    scenario = _scenario()
    asset = scenario.assets["AST-SITE-04-radio-unit"]
    asset.health = 0.1
    scenario._derive_asset_metrics(asset)
    scenario.apply_command(
        _command(
            "cmd-maintenance-2",
            "create_maintenance_work_order",
            {"asset_id": asset.id, "kind": "repair", "priority": 1},
            trace_id="trace-maintenance-2",
        )
    )
    stock = scenario.spare_stocks["SPARE-EAST-RADIO-UNIT"]
    prior_stock = stock.quantity

    accepted = scenario.apply_command(
        _command(
            "cmd-field-1",
            "dispatch_field_repair",
            {
                "work_order_id": "WO-00001",
                "technician_id": "TECH-EAST-01",
                "action": "repair",
            },
            trace_id="trace-field-1",
        )
    )

    assert accepted.type == "command.accepted"
    assert scenario.work_orders["WO-00001"].status == "completed"
    assert scenario.technicians["TECH-EAST-01"].status == "available"
    assert stock.quantity == prior_stock - 1
    assert asset.status == "healthy"
    assert asset.health >= 0.9
    repaired = _events(scenario, "asset.repaired")[-1]
    assert repaired.trace_id == "trace-field-1"
    assert repaired.cause_event_id == accepted.event_id


def test_field_dispatch_requires_approval_for_cross_region_spare():
    scenario = _scenario()
    asset = scenario.assets["AST-SITE-10-radio-unit"]
    asset.health = 0.1
    scenario._derive_asset_metrics(asset)
    scenario.apply_command(
        _command(
            "cmd-maintenance-west",
            "create_maintenance_work_order",
            {"asset_id": asset.id, "kind": "repair", "priority": 1},
            trace_id="trace-maintenance-west",
        )
    )
    field_sensor = _events(scenario, "sensor.tripped")[-1]
    observation = scenario.build_observation(
        field_sensor.to_dict(),
        now=scenario.runtime.now,
    )
    assert observation["spare_stock"]["quantity"] == 0
    assert any(
        stock["id"] == "SPARE-NORTH-RADIO-UNIT"
        for stock in observation["alternate_spare_stocks"]
    )

    rejected = scenario.apply_command(
        _command(
            "cmd-field-west-denied",
            "dispatch_field_repair",
            {
                "work_order_id": "WO-00001",
                "technician_id": "TECH-WEST-01",
                "source_stock_id": "SPARE-NORTH-RADIO-UNIT",
                "action": "repair",
            },
            trace_id="trace-field-west-denied",
        )
    )
    assert rejected.type == "command.rejected"

    prior_stock = scenario.spare_stocks["SPARE-NORTH-RADIO-UNIT"].quantity
    accepted = scenario.apply_command(
        _command(
            "cmd-field-west-approved",
            "dispatch_field_repair",
            {
                "work_order_id": "WO-00001",
                "technician_id": "TECH-WEST-01",
                "source_stock_id": "SPARE-NORTH-RADIO-UNIT",
                "action": "repair",
                "approval_decision": "approve",
            },
            trace_id="trace-field-west-approved",
        )
    )
    assert accepted.type == "command.accepted"
    assert (
        scenario.spare_stocks["SPARE-NORTH-RADIO-UNIT"].quantity
        == prior_stock - 1
    )


def test_capacity_recovery_releases_infeasible_order_with_a_fresh_trace():
    scenario = _scenario()
    scenario.inject_capacity_pressure("SITE-04", utilization=0.95)
    congestion_sensor = _events(scenario, "sensor.tripped")[-1]
    assert congestion_sensor.actor_id == "sensor:site_congestion"
    assert congestion_sensor.target_id == "SITE-04"

    order_id = scenario.submit_service_order(
        account_id="ACC-00004",
        product="business-premium",
        requested_site_id="SITE-04",
    )
    order = scenario.orders[order_id]
    assert order.status == "infeasible"

    site = scenario.sites["SITE-04"]
    increase = site.traffic_mbps / 0.8 - site.capacity_mbps
    accepted = scenario.apply_command(
        _command(
            "cmd-capacity-1",
            "apply_capacity_action",
            {
                "site_id": site.id,
                "action": "temporary_capacity",
                "capacity_increase_mbps": round(increase, 3),
            },
            trace_id="trace-capacity-1",
        )
    )

    assert accepted.type == "command.accepted"
    assert scenario.sites["SITE-04"].utilization <= 0.85
    assert order.status == "pending"
    stable = _events(scenario, "site.capacity.stable")[-1]
    order_sensors = [
        event
        for event in _events(scenario, "sensor.tripped")
        if event.actor_id == "sensor:service_order" and event.target_id == order_id
    ]
    assert len(order_sensors) == 1
    redrive = order_sensors[0]
    assert redrive.cause_event_id == stable.event_id
    assert redrive.trace_id != "trace-capacity-1"
    assert redrive.payload["parent_trace_id"] == "trace-capacity-1"


def test_new_cascade_commands_are_idempotent():
    scenario = _scenario()
    command = _command(
        "cmd-prestage-idempotent",
        "prestage_field_resources",
        {
            "region": "north",
            "technician_ids": ["TECH-NORTH-01"],
            "spare_part_kinds": ["power"],
        },
        trace_id="trace-idempotent",
    )

    first = scenario.apply_command(command)
    second = scenario.apply_command(command)

    assert second is first
    assert len(
        [
            event
            for event in _events(scenario, "resources.prestaged")
            if event.trace_id == command.trace_id
        ]
    ) == 1


def test_cascade_sensors_build_actor_backed_observations():
    scenario = _scenario()
    scenario.inject_weather_risk("east", 2.0, 10.0)
    outage_sensor = _events(scenario, "sensor.tripped")[-1]
    outage = scenario.build_observation(outage_sensor.to_dict(), now=scenario.runtime.now)
    assert outage["weather_event"]["region"] == "east"
    assert outage["available_technicians"]
    assert outage["allowed_commands"] == ["prestage_field_resources"]

    scenario.runtime.run_until(1.0)
    maintenance_sensor = next(
        event
        for event in _events(scenario, "sensor.tripped")
        if event.actor_id == "sensor:asset_failure_risk"
    )
    maintenance = scenario.build_observation(
        maintenance_sensor.to_dict(),
        now=scenario.runtime.now,
    )
    assert maintenance["asset"]["id"] == maintenance_sensor.target_id
    assert maintenance["site"]["region"] == "east"
    assert maintenance["allowed_commands"] == ["create_maintenance_work_order"]

    asset = scenario.assets[maintenance_sensor.target_id]
    asset.health = 0.1
    scenario._derive_asset_metrics(asset)
    scenario.apply_command(
        _command(
            "cmd-observation-maintenance",
            "create_maintenance_work_order",
            {"asset_id": asset.id, "kind": "repair", "priority": 1},
            trace_id=maintenance_sensor.trace_id,
        )
    )
    field_sensor = _events(scenario, "sensor.tripped")[-1]
    field = scenario.build_observation(field_sensor.to_dict(), now=scenario.runtime.now)
    assert field["work_order"]["id"] == field_sensor.target_id
    assert field["dispatchable_technicians"]
    assert field["allowed_commands"] == ["dispatch_field_repair"]

    scenario.inject_capacity_pressure("SITE-04", utilization=0.95)
    capacity_sensor = _events(scenario, "sensor.tripped")[-1]
    capacity = scenario.build_observation(
        capacity_sensor.to_dict(),
        now=scenario.runtime.now,
    )
    assert capacity["site"]["id"] == "SITE-04"
    assert capacity["allowed_commands"] == ["apply_capacity_action"]
