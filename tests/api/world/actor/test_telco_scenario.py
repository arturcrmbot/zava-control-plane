from verticals.telco.world import (
    NetworkConfig,
    SiteFailure,
    run_network,
)


def _small_config() -> NetworkConfig:
    return NetworkConfig(
        site_count=8,
        subscriber_count=400,
        session_count=480,
        site_capacity_mbps=600.0,
        simulation_minutes=60.0,
    )


def test_network_world_contains_real_sites_subscribers_and_sessions():
    scenario = run_network(seed=11, config=_small_config())
    assert len(scenario.sites) == 8
    assert len(scenario.subscribers) == 400
    assert len(scenario.sessions) == 480
    assert {e.type for e in scenario.runtime.journal} >= {
        "simulation.started", "site.created", "subscriber.created", "session.started",
    }


def test_every_site_has_real_neighbours_that_exist():
    scenario = run_network(seed=12, config=_small_config())
    for site in scenario.sites.values():
        assert site.neighbor_ids, f"{site.id} has no neighbours"
        for neighbor_id in site.neighbor_ids:
            assert neighbor_id in scenario.sites
            assert neighbor_id != site.id


def test_site_failure_is_a_real_journalled_perturbation_that_degrades_sessions():
    scenario = run_network(
        seed=13, config=_small_config(), failures=(SiteFailure(at_minute=5),),
    )
    failed = next(e for e in scenario.runtime.journal if e.type == "site.failed")
    site_id = failed.actor_id
    assert scenario.sites[site_id].status == "failed"
    # Every affected session became degraded and points back to the failed site.
    degraded = [e for e in scenario.runtime.journal if e.type == "session.degraded"]
    assert degraded
    for event in degraded:
        session = scenario.sessions[event.actor_id]
        assert session.status in {"degraded", "rerouted"}
        assert session.origin_site_id == site_id
        assert event.cause_event_id == failed.event_id


def test_failed_site_neighbours_take_real_reattach_congestion():
    scenario = run_network(
        seed=14, config=_small_config(), failures=(SiteFailure(at_minute=5),),
    )
    failed = next(e for e in scenario.runtime.journal if e.type == "site.failed")
    incident = scenario.sites[failed.actor_id]
    # At least one healthy neighbour recorded a reattach-congestion metric edge.
    congestion = [
        e for e in scenario.runtime.journal
        if e.type == "site.metrics" and e.payload.get("reason") == "reattach_congestion"
    ]
    assert congestion
    assert {e.actor_id for e in congestion} <= set(incident.neighbor_ids)


def test_every_causal_reference_points_to_an_earlier_event():
    scenario = run_network(
        seed=15, config=_small_config(), failures=(SiteFailure(at_minute=5),),
    )
    positions = {event.event_id: event.seq for event in scenario.runtime.journal}
    for event in scenario.runtime.journal:
        if event.cause_event_id:
            assert positions[event.cause_event_id] < event.seq


def test_default_failure_site_is_the_busiest_healthy_site():
    scenario = run_network(seed=16, config=_small_config())
    busiest = max(scenario.sites.values(), key=lambda s: (s.traffic_mbps, s.id))
    resolved = scenario._resolve_failure_site(None)
    assert resolved == busiest.id
