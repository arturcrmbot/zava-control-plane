"""Tests for the split network-incident deterministic activities.

The responder now runs two real deterministic boundaries — impact diagnosis
then reroute execution — that the orchestrator calls in order. ``_decide``
composes them exactly as the orchestrator does so the end-to-end reroute
determinism (voice-first, greedy capacity, explicit no-ops) is still asserted,
plus focused tests for each boundary.
"""
from api.functions.workflows.network_incident_activities import (
    network_incident_impact_activity,
    network_incident_reroute_activity,
)


def _decide(payload: dict) -> dict:
    """Compose impact → reroute exactly as the orchestrator does."""
    impact = network_incident_impact_activity(payload)
    return network_incident_reroute_activity({
        "trace_id": payload.get("trace_id"),
        "diagnosis": impact.get("diagnosis"),
        "diagnosis_reasoning": impact.get("reasoning"),
    })


def observation(*, voice=2, data=3, neighbours=None, incident="SITE-01"):
    if neighbours is None:
        neighbours = [
            {"id": "SITE-02", "status": "healthy", "spare_mbps": 100.0},
            {"id": "SITE-03", "status": "healthy", "spare_mbps": 50.0},
        ]
    sessions = [
        {"id": f"SESSION-V{i:03d}", "kind": "voice", "demand_mbps": 0.1}
        for i in range(voice)
    ]
    sessions += [
        {"id": f"SESSION-D{i:03d}", "kind": "data", "demand_mbps": 2.0}
        for i in range(data)
    ]
    return {
        "trace_id": "network-anomaly-SITE-01-42",
        "observation": {
            "incident_site": {"id": incident},
            "neighbor_sites": neighbours,
            "affected_sessions": sessions,
            "allowed_commands": ["reroute_sessions"],
        },
    }


# -- end-to-end (impact → reroute) determinism ------------------------------

def test_returns_a_typed_reroute_command_for_every_affected_session():
    out = _decide(observation())
    command = out["command"]
    assert command["type"] == "reroute_sessions"
    assert command["trace_id"] == "network-anomaly-SITE-01-42"
    assert command["payload"]["incident_site_id"] == "SITE-01"
    assert len(command["payload"]["assignments"]) == 5
    assert "planned 5 session assignments" in out["reasoning"]
    assert "rerouted" not in out["reasoning"]
    # Each session is assigned to a real neighbour, never the incident site.
    for a in command["payload"]["assignments"]:
        assert a["to_site_id"] in {"SITE-02", "SITE-03"}


def test_voice_sessions_are_prioritised_then_ordered_by_id():
    out = _decide(observation(voice=2, data=2))
    ids = [a["session_id"] for a in out["command"]["payload"]["assignments"]]
    # The two voice sessions come first, in deterministic id order.
    assert ids[:2] == ["SESSION-V000", "SESSION-V001"]


def test_each_session_goes_to_the_healthiest_neighbour_that_fits():
    # SITE-02 has the most spare, so the first (voice) session lands there.
    out = _decide(observation(voice=1, data=0))
    assert out["command"]["payload"]["assignments"][0]["to_site_id"] == "SITE-02"


def test_capacity_is_respected_and_overflow_is_reported():
    # One tiny neighbour that can hold only one 2mbps data session.
    neighbours = [{"id": "SITE-02", "status": "healthy", "spare_mbps": 2.0}]
    out = _decide(observation(voice=0, data=3, neighbours=neighbours))
    assignments = out["command"]["payload"]["assignments"]
    assert len(assignments) == 1
    assert "planned 1 session assignment" in out["reasoning"]
    assert "2 unassigned" in out["reasoning"]


def test_no_affected_sessions_returns_explicit_noop():
    out = _decide(observation(voice=0, data=0))
    assert out["command"] is None
    assert "no affected sessions" in out["reasoning"]


def test_no_healthy_neighbour_capacity_returns_explicit_noop():
    neighbours = [{"id": "SITE-02", "status": "failed", "spare_mbps": 100.0}]
    out = _decide(observation(voice=1, data=0, neighbours=neighbours))
    assert out["command"] is None
    assert "no healthy neighbour capacity" in out["reasoning"]


def test_missing_incident_site_returns_explicit_noop():
    payload = observation()
    payload["observation"]["incident_site"] = {}
    out = _decide(payload)
    assert out["command"] is None
    assert "no incident site" in out["reasoning"]


# -- impact diagnosis (deterministic boundary 1) ----------------------------

def test_impact_diagnosis_orders_voice_first_and_maps_spare():
    diag = network_incident_impact_activity(observation(voice=1, data=1))["diagnosis"]
    assert diag["incident_site_id"] == "SITE-01"
    assert diag["spare_capacity"] == {"SITE-02": 100.0, "SITE-03": 50.0}
    assert diag["affected_total"] == 2
    assert diag["affected_sessions"][0]["kind"] == "voice"


def test_impact_diagnosis_noops_return_no_diagnosis_with_reason():
    assert network_incident_impact_activity(observation(voice=0, data=0)) == {
        "diagnosis": None, "reasoning": "no affected sessions to reroute",
    }


# -- reroute planning (deterministic boundary 2) ---------------------------

def test_reroute_activity_passes_through_impact_noop_reason():
    out = network_incident_reroute_activity({
        "trace_id": "t-1", "diagnosis": None,
        "diagnosis_reasoning": "no healthy neighbour capacity available",
    })
    assert out["command"] is None
    assert out["reasoning"] == "no healthy neighbour capacity available"


def test_reroute_activity_builds_command_from_diagnosis():
    diagnosis = {
        "incident_site_id": "SITE-01",
        "spare_capacity": {"SITE-02": 5.0},
        "affected_sessions": [{"id": "SESSION-D000", "kind": "data", "demand_mbps": 2.0}],
        "affected_total": 1,
    }
    out = network_incident_reroute_activity({"trace_id": "t-9", "diagnosis": diagnosis})
    assert out["command"]["command_id"] == "cmd-t-9-reroute"
    assert out["command"]["payload"]["assignments"] == [
        {"session_id": "SESSION-D000", "to_site_id": "SITE-02"}
    ]
    assert out["reasoning"] == "incident at SITE-01: planned 1 session assignment across 1 neighbour"
