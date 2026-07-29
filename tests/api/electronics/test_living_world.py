from __future__ import annotations

from importlib import import_module

from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime


HERO_SKU = "SKU-APEX-X1-GRAPHITE-16"
SOURCE = "DC-UK-MID-01"
DESTINATION = "STORE-UK-LON-01"

# Required deterministic UK store/hub network (id -> (label, country)).
EXPECTED_LOCATIONS = {
    "STORE-UK-LON-01": ("London Central", "GB"),
    "STORE-UK-MAN-01": ("Manchester Trafford", "GB"),
    "STORE-UK-BHM-01": ("Birmingham Bullring", "GB"),
    "STORE-UK-LDS-01": ("Leeds Trinity", "GB"),
    "STORE-UK-BRS-01": ("Bristol Cabot", "GB"),
    "STORE-UK-GLA-01": ("Glasgow Braehead", "GB"),
    "STORE-UK-CDF-01": ("Cardiff Central", "GB"),
    "STORE-UK-BFS-01": ("Belfast Boucher", "GB"),
    "DC-UK-MID-01": ("Midlands Fulfilment Hub", "GB"),
    "DC-UK-SE-01": ("South East Delivery Hub", "GB"),
}


def _scenario(seed: int = 42):
    module = import_module("verticals.electronics.world")
    runtime = SimulationRuntime(seed)
    scenario = module.ElectronicsScenario(runtime)
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
            "reason_code": "LAUNCH_STOCK_IMBALANCE",
            "evidence_digest": "sha256:deterministic-electronics-evidence",
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


def test_all_store_and_hub_locations_match_the_uk_network() -> None:
    _, scenario = _scenario()
    state = scenario.render_state()

    seen = {
        item["id"]: (item["name"], item["country"])
        for item in (*state["stores"], *state["distribution_centres"])
    }
    assert seen == EXPECTED_LOCATIONS
    assert {
        item["country"] for item in (*state["stores"], *state["distribution_centres"])
    } == {"GB"}


def test_hero_product_and_sku_are_present_with_credible_electronics_identity() -> None:
    _, scenario = _scenario()
    state = scenario.render_state()

    hero_sku = next(item for item in state["skus"] if item["id"] == HERO_SKU)
    hero_style = next(
        item for item in state["styles"] if item["id"] == hero_sku["style_id"]
    )

    assert hero_style["name"] == "Apex X1 Gaming Laptop"
    assert hero_sku["colour"] == "GRAPHITE"
    assert hero_sku["size"] == "16"
    assert "season" not in hero_style["lifecycle"]
    assert "style" not in hero_style["name"].lower()


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
    assert sensor["payload"]["source_location_id"] == SOURCE
    assert sensor["payload"]["destination_location_id"] == DESTINATION

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


def test_hero_transfer_requires_approval_for_high_value_launch_stock_and_is_idempotent() -> None:
    _, scenario = _scenario()
    source = scenario.inventory[(SOURCE, HERO_SKU)]
    destination = scenario.inventory[(DESTINATION, HERO_SKU)]
    before = (source.on_hand, destination.on_hand, source.version, destination.version)

    rejected = scenario.apply_command(
        _hero_command(scenario, approval_reference=None)
    )
    assert rejected.type == "command.rejected"
    assert "approval" in rejected.payload["reason"]
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
    sku = "SKU-VOLT-X1-MIDNIGHT-14"
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
            "reason_code": "LAUNCH_STOCK_IMBALANCE",
            "evidence_digest": "sha256:auto-safe",
        },
    )

    result = scenario.apply_command(command)

    assert result.type == "command.accepted"
    assert any(
        event.type == "inventory.transferred" and event.trace_id == "trace-auto"
        for event in scenario.runtime.journal
    )


def test_reset_replays_the_same_seeded_world(tmp_path) -> None:
    from api.server.services.event_bus import EventBus
    from api.server.world.service import ActorWorldService
    from api.shared.vertical_loader import build_runtime

    vertical = build_runtime(
        {"ZAVA_VERTICAL": "electronics"},
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


def test_world_scene_locations_match_the_registered_uk_network() -> None:
    from verticals.electronics.worlds import ELECTRONICS_WORLD

    _, scenario = _scenario()
    state = scenario.render_state()

    world_ids = {
        item["id"] for item in (*state["stores"], *state["distribution_centres"])
    }
    scene_locations = ELECTRONICS_WORLD.scene["locations"]
    scene_ids = {location["id"] for location in scene_locations}

    assert scene_ids == world_ids

    scene_by_id = {location["id"]: location for location in scene_locations}
    for location_id, (label, country) in EXPECTED_LOCATIONS.items():
        scene_location = scene_by_id[location_id]
        assert scene_location["label"] == label
        assert scene_location["country"] == country

    assert {location["country"] for location in scene_locations} == {"GB"}


def test_world_scene_copy_reflects_the_electronics_launch_not_fashion() -> None:
    from verticals.electronics.worlds import ELECTRONICS_WORLD

    scene = ELECTRONICS_WORLD.scene
    stale_terms = ("Paris", "EU", "SKU-STYLE-01-BLK-M")
    haystack = " ".join(
        [
            scene["subtitle"],
            scene["knowledge_relationship_label"],
            *scene["knowledge_actor_ids"],
        ]
    )
    for term in stale_terms:
        assert term not in haystack, f"stale Fashion term {term!r} leaked into scene"

    assert "Apex X1" in scene["knowledge_relationship_label"]
    assert "Midlands Fulfilment Hub" in scene["knowledge_relationship_label"]
    assert "London Central" in scene["knowledge_relationship_label"]
    assert scene["knowledge_actor_ids"] == [
        HERO_SKU,
        "DC-UK-MID-01",
        "STORE-UK-LON-01",
    ]


def test_hero_transfer_observation_is_truthfully_domestic_and_value_driven() -> None:
    runtime, scenario = _scenario()
    runtime.run_until(60)
    sensor = next(
        event
        for event in runtime.canonical_journal()
        if event["type"] == "sensor.tripped"
        and event["actor_id"] == "sensor:inventory_imbalance"
    )

    observation = scenario.build_observation(sensor, now=runtime.now)

    transfer_candidate = observation["transfer_candidate"]
    assert transfer_candidate["cross_border"] is False

    policy = observation["policy"]
    assert policy["decision"] == "approval_required"
    reason = policy["reason"].lower()
    assert "cross-border" not in reason
    assert "cross border" not in reason
    assert "value" in reason or "limit" in reason


def test_all_customer_home_regions_derive_from_uk_store_locations() -> None:
    _, scenario = _scenario()
    state = scenario.render_state()

    expected_regions = {
        "London",
        "North West",
        "West Midlands",
        "Yorkshire and the Humber",
        "South West",
        "Scotland",
        "Wales",
        "Northern Ireland",
    }

    customer_regions = {c["home_region"] for c in state["customers"]}

    assert customer_regions.issubset(
        expected_regions
    ), f"Found invalid regions: {customer_regions - expected_regions}"
    assert "EU" not in customer_regions, "Found stale EU region in customer home_region"
