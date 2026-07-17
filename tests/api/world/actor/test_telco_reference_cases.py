from __future__ import annotations

from api.server.world.runtime import SimulationRuntime
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES
from verticals.telco.world import NetworkConfig, NetworkScenario


def _scenario() -> NetworkScenario:
    runtime = SimulationRuntime(71)
    scenario = NetworkScenario(
        runtime,
        NetworkConfig(
            site_count=12,
            subscriber_count=200,
            session_count=240,
            site_capacity_mbps=600.0,
            simulation_minutes=60.0,
        ),
    )
    scenario.install()
    return scenario


def test_every_standard_profile_opens_a_real_case_and_sensor():
    scenario = _scenario()

    for profile in STANDARD_PROCESS_PROFILES.values():
        result = scenario.run_reference_process(profile.workflow_type)
        case = scenario.process_cases[result["case_id"]]
        sensor = next(
            event
            for event in scenario.runtime.journal
            if event.event_id == result["sensor_event_id"]
        )

        assert case.workflow_type == profile.workflow_type
        assert case.status == "open"
        assert case.subject_ids
        assert case.facts
        assert case.allowed_actions == (profile.command_type,)
        assert sensor.actor_id == profile.sensor_id
        assert sensor.target_id == case.id
        assert sensor.cause_event_id == result["root_event_id"]


def test_reference_observation_exposes_case_tools_and_provenance():
    scenario = _scenario()
    profile = STANDARD_PROCESS_PROFILES["revenue-assurance"]
    result = scenario.run_reference_process(profile.workflow_type)
    sensor = next(
        event
        for event in scenario.runtime.journal
        if event.event_id == result["sensor_event_id"]
    )

    observation = scenario.build_observation(
        sensor.to_dict(),
        now=scenario.runtime.now,
    )

    assert observation["case"]["id"] == result["case_id"]
    assert observation["subject_actors"]
    assert observation["skills"] == list(profile.skills)
    assert observation["mcp_packs"] == list(profile.mcp_packs)
    assert observation["allowed_tools"] == list(profile.allowed_tools)
    assert observation["allowed_commands"] == [profile.command_type]
    assert observation["event_ids"] == [sensor.event_id]
    assert observation["trace_id"] == sensor.trace_id


def test_reference_cases_render_in_world_snapshot():
    scenario = _scenario()
    scenario.run_reference_process("billing-dispute-resolution")

    state = scenario.render_state()

    assert state["process_cases"][0]["workflow_type"] == (
        "billing-dispute-resolution"
    )
    assert state["process_cases"][0]["status"] == "open"
    assert len(state["process_library"]) == 37
    assert sum(
        item["maturity"] == "hero" for item in state["process_library"]
    ) == 9
    assert sum(
        item["maturity"] == "standard" for item in state["process_library"]
    ) == 28
