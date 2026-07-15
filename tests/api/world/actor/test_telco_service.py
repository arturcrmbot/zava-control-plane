"""Behavioural + integration proof for ActorWorldService.telco: the live telco
world paces the network incident and the REAL Durable decision activity closes
the loop (observe → decide → reroute) against actual session actors.
"""
from __future__ import annotations

import json

from api.functions.workflows.network_incident_activities import (
    network_incident_impact_activity,
    network_incident_reroute_activity,
)
from api.server.services.event_bus import EventBus
from api.server.world.model import SimulationCommand
from api.server.world.service import ActorWorldService


def _decide(trace_id: str, observation: dict) -> dict:
    """Compose the two REAL deterministic activities exactly as the
    NetworkIncidentOrchestrator does: impact diagnosis → reroute execution."""
    impact = network_incident_impact_activity(
        {"trace_id": trace_id, "observation": observation}
    )
    return network_incident_reroute_activity({
        "trace_id": trace_id,
        "diagnosis": impact.get("diagnosis"),
        "diagnosis_reasoning": impact.get("reasoning"),
    })


def service() -> ActorWorldService:
    return ActorWorldService.telco(seed=42, bus=EventBus(), minutes_per_second=1000)


def _command_from(decision: dict) -> SimulationCommand:
    cmd = decision["command"]
    return SimulationCommand(
        command_id=cmd["command_id"],
        trace_id=cmd["trace_id"],
        issued_by=cmd["issued_by"],
        type=cmd["type"],
        payload=cmd["payload"],
    )


def test_snapshot_contains_actual_actor_state_and_projection():
    world = service()
    snapshot = world.snapshot()
    assert snapshot["scenario"] == "telco"
    assert len(snapshot["sites"]) == 12
    assert len(snapshot["subscribers"]) == 2_000
    assert len(snapshot["sessions"]) == 2_200
    assert snapshot["projection"]["sites_total"] == 12
    assert snapshot["latest_seq"] == len(world.runtime.journal)
    json.dumps(snapshot)  # must not raise
    assert isinstance(snapshot["sites"][0]["neighbor_ids"], list)


def test_inject_site_failure_fails_a_real_site_and_trips_the_sensor():
    world = service()
    site_id = world.inject_site_failure()
    world.runtime.run_until(2)
    failed = next(e for e in world.runtime.journal if e.type == "site.failed")
    assert failed.actor_id == site_id
    assert world.scenario.sites[site_id].status == "failed"
    sensor = next(
        e for e in world.runtime.journal
        if e.type == "sensor.tripped" and e.actor_id == "sensor:network_anomaly"
    )
    assert sensor.payload["measurements"]["site_id"] == site_id


def test_full_incident_loop_reroutes_real_sessions_via_the_durable_activity():
    world = service()
    site_id = world.inject_site_failure()
    world.runtime.run_until(2)

    # Observe: build the exact observation the world bridge hands the orchestrator.
    sensor = next(
        e for e in world.runtime.journal
        if e.type == "sensor.tripped" and e.actor_id == "sensor:network_anomaly"
    )
    observation = world.build_observation(sensor.to_dict())
    assert observation["incident_site"]["id"] == site_id
    assert observation["affected_sessions"]
    assert observation["neighbor_sites"]

    # Decide: run the REAL Durable activities (no mocks), composed in order.
    decision = _decide(observation["trace_id"], observation)
    command = _command_from(decision)
    assert command.type == "reroute_sessions"
    assigned_ids = [a["session_id"] for a in command.payload["assignments"]]
    assert assigned_ids  # at least one session rerouted

    # Voice sessions are prioritised (placed before data/video in the order).
    kinds = [world.scenario.sessions[a["session_id"]].kind for a in command.payload["assignments"]]
    assert kinds == sorted(kinds, key=lambda k: 0 if k == "voice" else 1) or "voice" not in kinds

    # Reroute: apply through the live service and prove the causal chain.
    published: list[str] = []
    world.bus.on_any(lambda event: published.append(event.type))
    result = world.apply_command(command)
    assert result.type == "command.accepted"
    assert "world.command.accepted" in published
    assert "world.session.rerouted" in published
    assert "world.site.recovered" in published

    # Output command assignments EXACTLY equal the journalled session.rerouted.
    rerouted = [
        (e.actor_id, e.payload["to_site_id"])
        for e in world.runtime.journal if e.type == "session.rerouted"
    ]
    assert rerouted == [(a["session_id"], a["to_site_id"]) for a in command.payload["assignments"]]

    # Every rerouted session is now really anchored on its neighbour.
    for a in command.payload["assignments"]:
        session = world.scenario.sessions[a["session_id"]]
        assert session.status == "rerouted"
        assert session.site_id == a["to_site_id"]

    # Failed-site load drops to zero and it recovers to healthy.
    assert world.scenario.sites[site_id].status == "healthy"
    assert world.scenario.sites[site_id].traffic_mbps == 0.0


def test_full_incident_loop_changes_neighbour_load_and_is_idempotent():
    world = service()
    world.inject_site_failure()
    world.runtime.run_until(2)
    sensor = next(
        e for e in world.runtime.journal
        if e.type == "sensor.tripped" and e.actor_id == "sensor:network_anomaly"
    )
    observation = world.build_observation(sensor.to_dict())
    decision = _decide(observation["trace_id"], observation)
    command = _command_from(decision)

    target_ids = {a["to_site_id"] for a in command.payload["assignments"]}
    before = {sid: world.scenario.sites[sid].traffic_mbps for sid in target_ids}
    first = world.apply_command(command)
    after = {sid: world.scenario.sites[sid].traffic_mbps for sid in target_ids}
    # At least one neighbour actually took on more traffic.
    assert any(after[sid] > before[sid] for sid in target_ids)

    # Re-applying the same command_id is a no-op (idempotent).
    count = len(world.runtime.journal)
    second = world.apply_command(command)
    assert second.event_id == first.event_id
    assert len(world.runtime.journal) == count
