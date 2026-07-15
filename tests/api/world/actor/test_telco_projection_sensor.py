from api.server.world.packs.telco import NetworkConfig, SiteFailure, run_network
from api.server.world.projection import project_network


def _config() -> NetworkConfig:
    return NetworkConfig(
        site_count=8,
        subscriber_count=400,
        session_count=480,
        site_capacity_mbps=600.0,
        simulation_minutes=60.0,
    )


def test_projection_is_derived_from_actor_state():
    scenario = run_network(seed=21, config=_config())
    projection = project_network(scenario)
    assert projection.sites_total == len(scenario.sites)
    assert projection.subscribers_total == len(scenario.subscribers)
    assert projection.sessions_total == len(scenario.sessions)
    assert projection.sessions_active == sum(
        s.status == "active" for s in scenario.sessions.values()
    )
    assert projection.sites_healthy + projection.sites_failed == projection.sites_total
    assert 0.0 <= projection.average_utilization <= 2.0


def test_failed_world_trips_sensor_with_real_site_and_session_ids():
    scenario = run_network(
        seed=22, config=_config(), failures=(SiteFailure(at_minute=5),),
    )
    sensor = next(
        e for e in scenario.runtime.journal
        if e.type == "sensor.tripped" and e.actor_id == "sensor:network_anomaly"
    )
    failed = next(e for e in scenario.runtime.journal if e.type == "site.failed")
    assert sensor.trace_id == failed.trace_id
    measurements = sensor.payload["measurements"]
    site_id = measurements["site_id"]
    assert site_id in scenario.sites
    assert scenario.sites[site_id].status == "failed"
    assert measurements["affected_session_count"] >= 1
    # Every actor id named by the sensor is a real degraded session on the site.
    assert sensor.payload["actor_ids"]
    for session_id in sensor.payload["actor_ids"]:
        session = scenario.sessions[session_id]
        assert session.origin_site_id == site_id
    assert sensor.cause_event_id is not None


def test_projection_counts_rerouted_sessions_after_a_reroute():
    from api.server.world.model import SimulationCommand

    scenario = run_network(
        seed=23, config=_config(), failures=(SiteFailure(at_minute=5),),
    )
    failed = next(e for e in scenario.runtime.journal if e.type == "site.failed")
    incident_id = failed.actor_id
    degraded = [
        s for s in scenario.sessions.values()
        if s.status == "degraded" and s.origin_site_id == incident_id
    ]
    neighbor_id = next(
        n for n in scenario.sites[incident_id].neighbor_ids
        if scenario.sites[n].status == "healthy"
    )
    assignments = [{"session_id": s.id, "to_site_id": neighbor_id} for s in degraded]
    scenario.apply_command(
        SimulationCommand(
            command_id="cmd-proj",
            trace_id="trace-proj",
            issued_by="network_incident",
            type="reroute_sessions",
            payload={"incident_site_id": incident_id, "assignments": assignments},
        )
    )
    projection = project_network(scenario)
    assert projection.sessions_rerouted == len(degraded)
    assert projection.sessions_degraded == 0
