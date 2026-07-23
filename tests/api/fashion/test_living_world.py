from __future__ import annotations

from importlib import import_module

from api.server.services.event_bus import EventBus
from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from api.server.world.service import ActorWorldService
from api.shared.vertical_loader import build_runtime


HERO_SKU = "SKU-STYLE-01-BLK-M"
SOURCE = "STORE-EU-PAR-01"
DESTINATION = "STORE-UK-LON-01"


def _scenario(seed: int = 42):
    module = import_module("verticals.fashion.world")
    runtime = SimulationRuntime(seed)
    scenario = module.FashionScenario(runtime)
    scenario.install()
    return runtime, scenario


def _hero_command(
    scenario,
    *,
    command_id: str = "CMD-REBAL-001",
    source_version: int | None = None,
    destination_version: int | None = None,
    approval_reference: str | None = "HITL-MERCH-001",
    ownership: str = "owned",
) -> SimulationCommand:
    source = scenario.inventory[(SOURCE, HERO_SKU)]
    destination = scenario.inventory[(DESTINATION, HERO_SKU)]
    return SimulationCommand(
        command_id=command_id,
        trace_id="trace-rebalance",
        issued_by="merchandising-planning",
        type="inventory.transfer",
        payload={
            "workflow_id": "rebalance-evt-00000001",
            "source_location_id": SOURCE,
            "destination_location_id": DESTINATION,
            "sku_id": HERO_SKU,
            "quantity": 24,
            "ownership": ownership,
            "expected_source_version": (
                source.version if source_version is None else source_version
            ),
            "expected_destination_version": (
                destination.version
                if destination_version is None
                else destination_version
            ),
            "policy_decision": "approval_required",
            "approval_reference": approval_reference,
            "reason_code": "DEMAND_STOCK_IMBALANCE",
            "evidence_digest": "sha256:deterministic-fashion-evidence",
        },
    )


def test_seed_42_builds_the_signed_demo_scale_deterministically() -> None:
    first_runtime, first = _scenario()
    second_runtime, second = _scenario()

    first_runtime.run_until(42)
    second_runtime.run_until(42)

    state = first.render_state()
    assert len(state["stores"]) == 8
    assert len(state["distribution_centres"]) == 2
    assert len(state["brands"]) == 12
    assert len(state["styles"]) == 24
    assert len(state["skus"]) == 192
    assert len(state["customers"]) == 300
    assert len(state["demand_history"]) == 14
    assert first_runtime.canonical_journal() == second_runtime.canonical_journal()


def test_ordinary_retail_activity_precedes_real_threshold_sensor() -> None:
    runtime, scenario = _scenario()

    runtime.run_until(53)
    before = runtime.canonical_journal()
    assert not [event for event in before if event["type"] == "sensor.tripped"]
    assert any(event["type"] == "customer.entered" for event in before)
    assert any(event["type"] == "staff.served" for event in before)
    assert any(event["type"] == "order.placed" for event in before)
    assert any(event["type"] == "inventory.sold" for event in before)

    runtime.run_until(60)
    sensors = [
        event
        for event in runtime.canonical_journal()
        if event["type"] == "sensor.tripped"
        and event["actor_id"] == "sensor:inventory_imbalance"
    ]
    assert len(sensors) == 1
    sensor = sensors[0]
    assert sensor["sim_time"] >= 54
    assert sensor["target_id"] == HERO_SKU
    assert sensor["cause_event_id"] is not None
    assert sensor["payload"]["measurements"]["destination_available"] <= 8
    assert sensor["payload"]["measurements"]["source_available"] >= 60
    assert sensor["payload"]["threshold"]["crossed"] is True

    sensor_seq = sensor["seq"]
    runtime.run_until(110)
    later = [event for event in runtime.canonical_journal() if event["seq"] > sensor_seq]
    assert any(event["type"] == "customer.entered" for event in later)
    assert any(event["type"] == "order.placed" for event in later)


def test_hero_demand_and_stock_depletion_share_the_destination_store() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)
    hero_orders = [
        order for order in scenario.orders.values() if order.sku_id == HERO_SKU
    ]

    assert len(hero_orders) == 4
    assert {order.location_id for order in hero_orders} == {DESTINATION}
    for order in hero_orders:
        sale = next(
            event
            for event in runtime.journal
            if event.type == "inventory.sold" and event.target_id == order.id
        )
        assert sale.payload["location_id"] == order.location_id


def test_sustained_activity_records_stockouts_without_negative_inventory() -> None:
    runtime, scenario = _scenario()

    runtime.run_until(600)

    assert all(
        position.on_hand >= position.reserved
        for position in scenario.inventory.values()
    )
    assert any(event.type == "inventory.stockout" for event in runtime.journal)
    assert all(
        event.payload["available"] >= 0
        for event in runtime.journal
        if event.type == "inventory.sold"
    )


def test_departed_customers_leave_the_spatial_store_world() -> None:
    runtime, scenario = _scenario()

    runtime.run_until(12)

    departed = [
        customer
        for customer in scenario.customers.values()
        if customer.status == "departed"
    ]
    assert departed
    assert {customer.location_id for customer in departed} == {"OFFSITE"}
    exit_events = [
        event for event in runtime.journal if event.type == "customer.moved"
    ]
    assert exit_events
    assert all(event.target_id == "OFFSITE" for event in exit_events)
    assert all(
        event.payload["location_id"] == "OFFSITE" for event in exit_events
    )


def test_visible_actor_transitions_reference_real_ids() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)
    state = scenario.render_state()
    known_ids = {
        *(item["id"] for key in ("stores", "distribution_centres") for item in state[key]),
        *(item["id"] for key in ("customers", "staff", "orders") for item in state[key]),
        *(item["id"] for key in ("deliveries", "returns", "inventory_tokens") for item in state[key]),
        *(item["id"] for item in state["skus"]),
    }

    visible_types = {
        "customer.entered",
        "customer.moved",
        "staff.served",
        "order.placed",
        "order.cancelled",
        "inventory.sold",
        "delivery.arrived",
        "return.received",
    }
    visible = [event for event in runtime.journal if event.type in visible_types]

    assert visible
    for event in visible:
        assert event.actor_id in known_ids
        assert event.event_id
        assert event.trace_id


def test_cross_border_transfer_requires_authority_and_is_idempotent() -> None:
    _, scenario = _scenario()
    source = scenario.inventory[(SOURCE, HERO_SKU)]
    destination = scenario.inventory[(DESTINATION, HERO_SKU)]
    before = (source.on_hand, destination.on_hand, source.version, destination.version)

    rejected = scenario.apply_command(
        _hero_command(scenario, approval_reference=None)
    )
    assert rejected.type == "command.rejected"
    assert rejected.payload["reason"] == "cross-border transfer requires approval"
    assert (source.on_hand, destination.on_hand, source.version, destination.version) == before

    accepted = scenario.apply_command(_hero_command(scenario))
    assert accepted.type == "command.accepted"
    assert source.on_hand == before[0] - 24
    assert destination.on_hand == before[1] + 24
    assert source.version == before[2] + 1
    assert destination.version == before[3] + 1
    assert scenario.knowledge_relationships[-1]["workflow_id"] == (
        "rebalance-evt-00000001"
    )

    duplicate = scenario.apply_command(_hero_command(scenario))
    assert duplicate.type == "command.duplicate"
    assert source.on_hand == before[0] - 24
    assert destination.on_hand == before[1] + 24


def test_transfer_fails_closed_for_ownership_versions_and_safety_stock() -> None:
    _, scenario = _scenario()

    wrong_owner = scenario.apply_command(
        _hero_command(scenario, command_id="CMD-OWNER", ownership="marketplace")
    )
    assert wrong_owner.type == "command.rejected"
    assert "owned inventory" in wrong_owner.payload["reason"]

    stale = scenario.apply_command(
        _hero_command(scenario, command_id="CMD-STALE", source_version=999)
    )
    assert stale.type == "command.rejected"
    assert "stale source version" in stale.payload["reason"]

    scenario.inventory[(SOURCE, HERO_SKU)].on_hand = 42
    unsafe = scenario.apply_command(
        _hero_command(scenario, command_id="CMD-UNSAFE")
    )
    assert unsafe.type == "command.rejected"
    assert "safety stock" in unsafe.payload["reason"]


def test_policy_safe_domestic_transfer_can_auto_execute() -> None:
    _, scenario = _scenario()
    sku = "SKU-STYLE-02-RED-S"
    source_id = "DC-UK-MID-01"
    destination_id = "STORE-UK-MAN-01"
    source = scenario.inventory[(source_id, sku)]
    destination = scenario.inventory[(destination_id, sku)]
    command = SimulationCommand(
        command_id="CMD-AUTO-001",
        trace_id="trace-auto",
        issued_by="merchandising-planning",
        type="inventory.transfer",
        payload={
            "workflow_id": "rebalance-auto-001",
            "source_location_id": source_id,
            "destination_location_id": destination_id,
            "sku_id": sku,
            "quantity": 12,
            "ownership": "owned",
            "expected_source_version": source.version,
            "expected_destination_version": destination.version,
            "policy_decision": "auto_safe",
            "approval_reference": None,
            "reason_code": "DEMAND_STOCK_IMBALANCE",
            "evidence_digest": "sha256:auto-safe",
        },
    )

    result = scenario.apply_command(command)

    assert result.type == "command.accepted"
    assert any(
        event.type == "inventory.transferred" and event.trace_id == "trace-auto"
        for event in scenario.runtime.journal
    )


def test_world_service_closes_objective_from_transfer_evidence(tmp_path) -> None:
    vertical = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    )
    service = ActorWorldService.for_runtime(
        vertical,
        seed=42,
        bus=EventBus(),
        speed=1_000,
    )
    service.runtime.run_until(60)
    sensor = next(
        event.to_dict()
        for event in service.runtime.journal
        if event.type == "sensor.tripped"
        and event.actor_id == "sensor:inventory_imbalance"
    )
    route = next(
        route
        for route in service.registration.objective_routes
        if route.sensor_id == "sensor:inventory_imbalance"
    )
    objective = service.open_objective(
        sensor,
        route,
        owner_function="merchandising-planning",
    )
    service.transition_objective(
        objective.id,
        "claimed",
        claimed_by="merchandising-planning",
    )
    service.transition_objective(objective.id, "acting")
    command = _hero_command(service.scenario)
    command = SimulationCommand(
        command_id=command.command_id,
        trace_id=objective.trace_id,
        issued_by="merchandising-planning",
        type=command.type,
        payload=command.payload,
    )

    result = service.apply_typed_command(objective, command)

    assert result.type == "command.accepted"
    assert service.objectives.get(objective.id).status == "resolved"
    assert service.evaluator.for_objective(objective.id).status == "resolved"


def test_hero_observation_freezes_inventory_versions_for_typed_command() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)
    sensor = next(
        event.to_dict()
        for event in runtime.journal
        if event.type == "sensor.tripped"
        and event.actor_id == "sensor:inventory_imbalance"
    )

    observation = scenario.build_observation(sensor, now=runtime.now)
    candidate = observation["transfer_candidate"]

    assert candidate["expected_source_version"] == (
        scenario.inventory[(SOURCE, HERO_SKU)].version
    )
    assert candidate["expected_destination_version"] == (
        scenario.inventory[(DESTINATION, HERO_SKU)].version
    )


def test_each_supporting_process_emits_its_own_sensor_and_mutation() -> None:
    _, scenario = _scenario()
    profiles = import_module(
        "verticals.fashion.process_profiles"
    ).FASHION_PROCESS_PROFILES

    for workflow_type in tuple(profiles)[1:]:
        trigger = scenario.run_reference_process(workflow_type)
        profile = profiles[workflow_type]
        event = scenario.runtime.journal[-1]
        assert trigger["event_id"] == event.event_id
        assert event.type == "sensor.tripped"
        assert event.actor_id == profile.sensor_id
        command = scenario.command_for_reference_process(
            workflow_type,
            trace_id=event.trace_id,
            workflow_id=f"{profile.prefix}-{event.event_id}",
            approval_decision="approve",
        )
        result = scenario.apply_command(command)
        assert result.type == "command.accepted"
        assert any(
            item.type == profile.success_event
            and item.trace_id == command.trace_id
            for item in scenario.runtime.journal
        )


def test_reset_replays_the_same_seeded_world(tmp_path) -> None:
    vertical = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    )
    service = ActorWorldService.for_runtime(
        vertical,
        seed=42,
        bus=EventBus(),
        speed=1_000,
    )
    service.runtime.run_until(60)
    first = service.runtime.canonical_journal()

    service.reset(42)
    service.runtime.run_until(60)

    assert service.runtime.canonical_journal() == first
