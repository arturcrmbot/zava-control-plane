"""Actor-level proof for Telco operational world state: real network assets,
weather events, technicians, and regional spare stock — the substrate later
outage, maintenance, field-dispatch, ticket and retention workflows depend on.

Task 1 only: no sensors/objectives wired for these actors yet, so tests stay
scoped to actor state, deterministic dynamics and the scenario injectors.
"""
from __future__ import annotations

import json
import typing

import pytest

from api.server.world.runtime import SimulationRuntime
from verticals.telco.operations import WorkOrder
from verticals.telco.world import (
    ASSET_KINDS,
    NetworkConfig,
    NetworkScenario,
    REGIONS,
    run_network,
)


def _config(simulation_minutes: float = 30.0) -> NetworkConfig:
    return NetworkConfig(
        site_count=12,
        subscriber_count=200,
        session_count=240,
        site_capacity_mbps=600.0,
        simulation_minutes=simulation_minutes,
    )


def _scenario(seed: int = 42, simulation_minutes: float = 30.0) -> NetworkScenario:
    return run_network(seed=seed, config=_config(simulation_minutes))


def _installed(seed: int, simulation_minutes: float) -> NetworkScenario:
    """Install without auto-running, so tests can inject mid-simulation and
    keep pacing manually (mirrors ActorWorldService's own install pattern)."""
    runtime = SimulationRuntime(seed)
    scenario = NetworkScenario(runtime, _config(simulation_minutes))
    scenario.install()
    return scenario


# -- creation / counts -------------------------------------------------------


def test_install_creates_48_assets_four_kinds_per_site():
    scenario = _scenario()
    assert len(scenario.assets) == 48
    for site_id in scenario.sites:
        kinds = {
            asset.kind for asset in scenario.assets.values() if asset.site_id == site_id
        }
        assert kinds == set(ASSET_KINDS)
    for kind in ASSET_KINDS:
        expected_id = f"AST-SITE-01-{kind}"
        assert expected_id in scenario.assets
        asset = scenario.assets[expected_id]
        assert asset.site_id == "SITE-01"
        assert asset.kind == kind
        assert 0.0 <= asset.health <= 1.0
        assert asset.status == "healthy"
        assert asset.risk_band == "healthy"


def test_install_creates_20_technicians_five_per_region():
    scenario = _scenario()
    assert len(scenario.technicians) == 20
    for region in REGIONS:
        regional = [t for t in scenario.technicians.values() if t.region == region]
        assert len(regional) == 5
        expected_ids = {f"TECH-{region.upper()}-{slot:02d}" for slot in range(1, 6)}
        assert {t.id for t in regional} == expected_ids


def test_install_creates_regional_spare_stock_for_four_part_kinds():
    scenario = _scenario()
    assert len(scenario.spare_stocks) == 16
    for region in REGIONS:
        for kind in ASSET_KINDS:
            stock_id = f"SPARE-{region.upper()}-{kind.upper()}"
            assert stock_id in scenario.spare_stocks
            stock = scenario.spare_stocks[stock_id]
            assert stock.region == region
            assert stock.part_kind == kind


# -- hero constraints ---------------------------------------------------------


def test_hero_technician_tech_west_05_is_unavailable():
    scenario = _scenario()
    technician = scenario.technicians["TECH-WEST-05"]
    assert technician.status == "unavailable"
    assert technician.region == "west"
    other_west = [
        t for t in scenario.technicians.values()
        if t.region == "west" and t.id != "TECH-WEST-05"
    ]
    assert all(t.status == "available" for t in other_west)


def test_hero_west_radio_unit_spare_stock_is_zero():
    scenario = _scenario()
    stock = scenario.spare_stocks["SPARE-WEST-RADIO-UNIT"]
    assert stock.quantity == 0
    # Sibling regional stock for the same part kind is healthy.
    assert scenario.spare_stocks["SPARE-NORTH-RADIO-UNIT"].quantity > 0


# -- determinism --------------------------------------------------------------


def test_same_seed_produces_identical_operational_actors():
    left = _scenario(seed=7)
    right = _scenario(seed=7)
    assert left.render_state()["assets"] == right.render_state()["assets"]
    assert left.render_state()["technicians"] == right.render_state()["technicians"]
    assert left.render_state()["spare_stocks"] == right.render_state()["spare_stocks"]


def test_same_seed_and_injection_produce_identical_journal_and_actors():
    left = _installed(seed=9, simulation_minutes=15.0)
    right = _installed(seed=9, simulation_minutes=15.0)
    left.inject_weather_risk("east", 1.5, 5.0)
    right.inject_weather_risk("east", 1.5, 5.0)
    left.runtime.run_until(15.0)
    right.runtime.run_until(15.0)
    assert left.runtime.canonical_journal() == right.runtime.canonical_journal()
    assert left.render_state()["assets"] == right.render_state()["assets"]


# -- weather dynamics -----------------------------------------------------


def test_weather_risk_elevates_failure_probability_only_in_target_region():
    baseline = _installed(seed=5, simulation_minutes=15.0)
    baseline.runtime.run_until(15.0)

    perturbed = _installed(seed=5, simulation_minutes=15.0)
    event_id = perturbed.inject_weather_risk("east", 1.5, 5.0)
    assert event_id
    perturbed.runtime.run_until(15.0)

    for asset_id, asset in perturbed.assets.items():
        base_asset = baseline.assets[asset_id]
        if perturbed.sites[asset.site_id].region == "east":
            assert asset.failure_probability >= base_asset.failure_probability
        else:
            assert asset.failure_probability == base_asset.failure_probability


def test_weather_event_expires_after_its_window():
    scenario = _installed(seed=6, simulation_minutes=20.0)
    scenario.inject_weather_risk("north", 2.0, 6.0)
    # Sampled while the window is still active (starts_at=0, ends_at=6).
    scenario.runtime.run_until(3.0)
    peak = {
        asset_id: asset.failure_probability
        for asset_id, asset in scenario.assets.items()
        if scenario.sites[asset.site_id].region == "north"
    }
    scenario.runtime.run_until(20.0)
    after = {
        asset_id: asset.failure_probability
        for asset_id, asset in scenario.assets.items()
        if scenario.sites[asset.site_id].region == "north"
    }
    assert any(after[k] < peak[k] for k in peak)


def test_inject_weather_risk_validates_region_and_bounds():
    scenario = _scenario()
    with pytest.raises(ValueError):
        scenario.inject_weather_risk("nowhere", 1.0, 10.0)
    with pytest.raises(ValueError):
        scenario.inject_weather_risk("north", 0.0, 10.0)
    with pytest.raises(ValueError):
        scenario.inject_weather_risk("north", 1.0, 0.0)
    with pytest.raises(ValueError):
        scenario.inject_weather_risk("north", float("inf"), 10.0)


# -- asset.metrics only on risk-band transition -----------------------------


def test_asset_metrics_emitted_only_on_risk_band_transitions():
    scenario = _installed(seed=8, simulation_minutes=10.0)
    scenario.inject_weather_risk("south", 2.0, 4.0)
    scenario.runtime.run_until(10.0)

    metrics_events = [e for e in scenario.runtime.journal if e.type == "asset.metrics"]
    # Far fewer transition events than (asset_count * ticks) would be if every
    # tick emitted.
    assert 0 < len(metrics_events) < 48 * 10
    by_actor: dict[str, list[str]] = {}
    for event in metrics_events:
        by_actor.setdefault(event.actor_id, []).append(event.payload["risk_band"])
    for bands in by_actor.values():
        # No two consecutive emissions report the same band.
        assert all(a != b for a, b in zip(bands, bands[1:]))


def test_asset_metrics_payload_uses_risk_band_and_preserves_lifecycle_status():
    scenario = _installed(seed=8, simulation_minutes=10.0)
    scenario.inject_weather_risk("south", 2.0, 4.0)
    scenario.runtime.run_until(10.0)

    metrics_events = [e for e in scenario.runtime.journal if e.type == "asset.metrics"]
    assert metrics_events
    for event in metrics_events:
        assert "risk_band" in event.payload
        assert "prior_risk_band" in event.payload
        assert event.payload["risk_band"] != event.payload["prior_risk_band"]
        # Risk derivation never overwrites lifecycle state. The maintenance
        # sensor may separately latch an actionable asset as degraded.
        assert event.payload["status"] in {"healthy", "degraded"}


# -- status/risk_band separation ----------------------------------------------


def test_network_asset_has_separate_lifecycle_status_and_risk_band_fields():
    scenario = _scenario()
    asset = next(iter(scenario.assets.values()))
    assert hasattr(asset, "status")
    assert hasattr(asset, "risk_band")


def test_all_assets_start_with_healthy_risk_band_and_lifecycle_status():
    scenario = _installed(seed=11, simulation_minutes=5.0)
    for asset in scenario.assets.values():
        assert asset.status == "healthy"
        assert asset.risk_band == "healthy"


def test_setting_asset_status_maintenance_survives_metric_derivation():
    scenario = _installed(seed=12, simulation_minutes=5.0)
    asset = next(iter(scenario.assets.values()))
    asset.status = "maintenance"
    prior_risk_band = asset.risk_band

    # Force a large health drop so risk-band derivation clearly moves.
    asset.health = 0.05
    scenario._derive_asset_metrics(asset)

    assert asset.status == "maintenance"  # lifecycle status untouched
    assert asset.risk_band != prior_risk_band  # risk band updates independently


def test_work_order_priority_is_typed_int_not_str():
    hints = typing.get_type_hints(WorkOrder)
    assert hints["priority"] is int
    order = WorkOrder(
        id="WO-0001",
        site_id="SITE-01",
        asset_id="AST-SITE-01-radio-unit",
        kind="repair",
        priority=1,
        required_skill="radio-unit",
        required_spare="radio-unit",
        due_at=10.0,
    )
    assert isinstance(order.priority, int)


# -- deterministic asset heterogeneity ----------------------------------------


def test_asset_health_is_seeded_heterogeneously_within_approved_range():
    scenario = _installed(seed=13, simulation_minutes=5.0)
    healths = [asset.health for asset in scenario.assets.values()]
    assert len(set(healths)) > 1
    assert all(0.72 <= h <= 0.99 for h in healths)


def test_asset_load_equals_site_utilization_at_install():
    scenario = _installed(seed=14, simulation_minutes=5.0)
    for asset in scenario.assets.values():
        site = scenario.sites[asset.site_id]
        assert asset.load == round(site.utilization, 4)


def test_asset_ids_use_lowercase_kind_stable_pattern():
    scenario = _scenario()
    for site_id in scenario.sites:
        for kind in ASSET_KINDS:
            expected_id = f"AST-{site_id}-{kind}"
            assert expected_id in scenario.assets
            assert kind.islower() or "-" in kind


# -- injection validation / idempotent semantics -----------------------------


def test_inject_spare_shortage_sets_quantity_zero_and_rejects_already_zero():
    scenario = _scenario()
    stock_id = scenario.inject_spare_shortage("east", "power")
    assert stock_id == "SPARE-EAST-POWER"
    assert scenario.spare_stocks[stock_id].quantity == 0

    with pytest.raises(ValueError):
        scenario.inject_spare_shortage("east", "power")  # already zero
    with pytest.raises(ValueError):
        scenario.inject_spare_shortage("west", "radio-unit")  # hero already zero
    with pytest.raises(ValueError):
        scenario.inject_spare_shortage("nowhere", "power")
    with pytest.raises(ValueError):
        scenario.inject_spare_shortage("east", "not-a-part")


def test_inject_technician_unavailable_sets_status_and_rejects_unhealthy_state():
    scenario = _scenario()
    technician_id = scenario.inject_technician_unavailable("TECH-NORTH-01")
    assert technician_id == "TECH-NORTH-01"
    assert scenario.technicians["TECH-NORTH-01"].status == "unavailable"

    with pytest.raises(ValueError):
        scenario.inject_technician_unavailable("TECH-NORTH-01")  # already unavailable
    with pytest.raises(ValueError):
        scenario.inject_technician_unavailable("TECH-WEST-05")  # hero already unavailable
    with pytest.raises(ValueError):
        scenario.inject_technician_unavailable("TECH-NOPE-99")


# -- snapshot / render_state --------------------------------------------------


def test_render_state_includes_new_json_safe_collections():
    scenario = _scenario()
    state = scenario.render_state()
    for key in (
        "assets",
        "weather_events",
        "work_orders",
        "technicians",
        "spare_stocks",
        "tickets",
        "experience_episodes",
        "retention_offers",
    ):
        assert key in state
    assert len(state["assets"]) == 48
    assert len(state["technicians"]) == 20
    assert len(state["spare_stocks"]) == 16
    # Actors created only by later-task workflows are valid as empty lists.
    assert state["work_orders"] == []
    assert state["tickets"] == []
    assert state["experience_episodes"] == []
    assert state["retention_offers"] == []
    assert state["weather_events"] == []
    json.dumps(state)  # must not raise
