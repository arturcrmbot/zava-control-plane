from api.server.world.model import SimulationCommand
from api.server.world.packs.telco import NetworkConfig, SiteFailure, run_network


def _degraded_world():
    """A completed small run with one failed site and its degraded sessions."""
    scenario = run_network(
        seed=31,
        config=NetworkConfig(
            site_count=8,
            subscriber_count=400,
            session_count=480,
            site_capacity_mbps=600.0,
            simulation_minutes=60.0,
        ),
        failures=(SiteFailure(at_minute=5),),
    )
    failed = next(e for e in scenario.runtime.journal if e.type == "site.failed")
    incident_id = failed.actor_id
    degraded = sorted(
        (s for s in scenario.sessions.values()
         if s.status == "degraded" and s.origin_site_id == incident_id),
        key=lambda s: s.id,
    )
    neighbor_id = next(
        n for n in scenario.sites[incident_id].neighbor_ids
        if scenario.sites[n].status == "healthy"
    )
    return scenario, incident_id, degraded, neighbor_id


def _command(incident_id, assignments, command_id="cmd-1"):
    return SimulationCommand(
        command_id=command_id,
        trace_id="trace-1",
        issued_by="network_incident",
        type="reroute_sessions",
        payload={"incident_site_id": incident_id, "assignments": assignments},
    )


def test_valid_command_moves_actual_sessions_and_journals_each_move():
    scenario, incident_id, degraded, neighbor_id = _degraded_world()
    picks = degraded[:3]
    assignments = [{"session_id": s.id, "to_site_id": neighbor_id} for s in picks]
    result = scenario.apply_command(_command(incident_id, assignments))
    assert result.type == "command.accepted"
    moved = [e.actor_id for e in scenario.runtime.journal if e.type == "session.rerouted"]
    assert moved == [s.id for s in picks]
    for s in picks:
        assert scenario.sessions[s.id].status == "rerouted"
        assert scenario.sessions[s.id].site_id == neighbor_id
        assert s.id in scenario.sites[neighbor_id].session_ids


def test_assignments_exactly_equal_the_journalled_reroutes():
    scenario, incident_id, degraded, neighbor_id = _degraded_world()
    assignments = [{"session_id": s.id, "to_site_id": neighbor_id} for s in degraded[:5]]
    scenario.apply_command(_command(incident_id, assignments))
    journalled = [
        (e.actor_id, e.payload["to_site_id"])
        for e in scenario.runtime.journal if e.type == "session.rerouted"
    ]
    assert journalled == [(a["session_id"], a["to_site_id"]) for a in assignments]


def test_invalid_command_is_all_or_nothing():
    scenario, incident_id, degraded, neighbor_id = _degraded_world()
    assignments = [
        {"session_id": degraded[0].id, "to_site_id": neighbor_id},
        {"session_id": "SESSION-MISSING", "to_site_id": neighbor_id},
    ]
    result = scenario.apply_command(_command(incident_id, assignments))
    assert result.type == "command.rejected"
    assert scenario.sessions[degraded[0].id].status == "degraded"
    assert not any(e.type == "session.rerouted" for e in scenario.runtime.journal)


def test_capacity_is_enforced_atomically():
    scenario, incident_id, degraded, neighbor_id = _degraded_world()
    # Saturate the neighbour so it cannot absorb even one more session.
    scenario.sites[neighbor_id].traffic_mbps = scenario.sites[neighbor_id].capacity_mbps
    assignments = [{"session_id": degraded[0].id, "to_site_id": neighbor_id}]
    result = scenario.apply_command(_command(incident_id, assignments))
    assert result.type == "command.rejected"
    assert "insufficient capacity" in result.payload["reason"]
    assert scenario.sessions[degraded[0].id].status == "degraded"


def test_cannot_reroute_back_onto_the_incident_site():
    scenario, incident_id, degraded, _neighbor_id = _degraded_world()
    assignments = [{"session_id": degraded[0].id, "to_site_id": incident_id}]
    result = scenario.apply_command(_command(incident_id, assignments))
    assert result.type == "command.rejected"


def test_duplicate_command_is_idempotent():
    scenario, incident_id, degraded, neighbor_id = _degraded_world()
    assignments = [{"session_id": degraded[0].id, "to_site_id": neighbor_id}]
    first = scenario.apply_command(_command(incident_id, assignments))
    count = len(scenario.runtime.journal)
    second = scenario.apply_command(_command(incident_id, assignments))
    assert second.event_id == first.event_id
    assert len(scenario.runtime.journal) == count


def test_reroute_recovers_the_incident_site():
    scenario, incident_id, degraded, neighbor_id = _degraded_world()
    assignments = [{"session_id": s.id, "to_site_id": neighbor_id} for s in degraded]
    scenario.apply_command(_command(incident_id, assignments))
    recovered = next(e for e in scenario.runtime.journal if e.type == "site.recovered")
    assert recovered.actor_id == incident_id
    assert scenario.sites[incident_id].status == "healthy"
    assert scenario.sites[incident_id].traffic_mbps == 0.0
