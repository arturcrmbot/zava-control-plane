from api.functions.workflows.network_incident_activities import (
    network_incident_decide_activity,
)


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


def test_returns_a_typed_reroute_command_for_every_affected_session():
    out = network_incident_decide_activity(observation())
    command = out["command"]
    assert command["type"] == "reroute_sessions"
    assert command["trace_id"] == "network-anomaly-SITE-01-42"
    assert command["payload"]["incident_site_id"] == "SITE-01"
    assert len(command["payload"]["assignments"]) == 5
    # Each session is assigned to a real neighbour, never the incident site.
    for a in command["payload"]["assignments"]:
        assert a["to_site_id"] in {"SITE-02", "SITE-03"}


def test_voice_sessions_are_prioritised_then_ordered_by_id():
    out = network_incident_decide_activity(observation(voice=2, data=2))
    ids = [a["session_id"] for a in out["command"]["payload"]["assignments"]]
    # The two voice sessions come first, in deterministic id order.
    assert ids[:2] == ["SESSION-V000", "SESSION-V001"]


def test_each_session_goes_to_the_healthiest_neighbour_that_fits():
    # SITE-02 has the most spare, so the first (voice) session lands there.
    out = network_incident_decide_activity(observation(voice=1, data=0))
    assert out["command"]["payload"]["assignments"][0]["to_site_id"] == "SITE-02"


def test_capacity_is_respected_and_overflow_is_reported():
    # One tiny neighbour that can hold only one 2mbps data session.
    neighbours = [{"id": "SITE-02", "status": "healthy", "spare_mbps": 2.0}]
    out = network_incident_decide_activity(
        observation(voice=0, data=3, neighbours=neighbours)
    )
    assignments = out["command"]["payload"]["assignments"]
    assert len(assignments) == 1
    assert "2 dropped" in out["reasoning"]


def test_no_affected_sessions_returns_explicit_noop():
    out = network_incident_decide_activity(observation(voice=0, data=0))
    assert out["command"] is None
    assert "no affected sessions" in out["reasoning"]


def test_no_healthy_neighbour_capacity_returns_explicit_noop():
    neighbours = [{"id": "SITE-02", "status": "failed", "spare_mbps": 100.0}]
    out = network_incident_decide_activity(
        observation(voice=1, data=0, neighbours=neighbours)
    )
    assert out["command"] is None
    assert "no healthy neighbour capacity" in out["reasoning"]


def test_missing_incident_site_returns_explicit_noop():
    payload = observation()
    payload["observation"]["incident_site"] = {}
    out = network_incident_decide_activity(payload)
    assert out["command"] is None
    assert "no incident site" in out["reasoning"]
