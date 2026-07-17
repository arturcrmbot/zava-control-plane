from __future__ import annotations

import pytest

from api.server.world.runtime import SimulationRuntime
from verticals.telco.world import NetworkConfig, NetworkScenario


SCENARIOS = {
    "storm-cascade": "sensor:outage_risk",
    "maintenance-save": "sensor:asset_failure_risk",
    "capacity-revenue": "sensor:site_congestion",
    "vulnerable-retention": "sensor:ticket_pressure",
}


def _scenario(seed: int = 61) -> NetworkScenario:
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


@pytest.mark.parametrize("name,expected_sensor", SCENARIOS.items())
def test_telco_scenario_injects_only_exogenous_state(name, expected_sensor):
    scenario = _scenario()
    before = len(scenario.runtime.journal)

    result = scenario.run_scenario(name)

    new_events = scenario.runtime.journal[before:]
    assert result["seed"] == 61
    assert result["root_event_id"] in {event.event_id for event in new_events}
    assert result["expected_first_sensor"] == expected_sensor
    assert any(
        event.type == "sensor.tripped" and event.actor_id == expected_sensor
        for event in new_events
    )
    assert not any(
        event.type.startswith("workflow.")
        or event.type in {
            "command.accepted",
            "resources.prestaged",
            "work_order.created",
            "asset.repaired",
            "asset.replaced",
            "site.capacity.stable",
            "ticket_batch.resolved",
            "retention_offer.issued",
        }
        for event in new_events
    )
