from __future__ import annotations

from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES
from verticals.telco.world import NetworkConfig, NetworkScenario


def _scenario(seed: int) -> NetworkScenario:
    runtime = SimulationRuntime(seed)
    scenario = NetworkScenario(
        runtime,
        NetworkConfig(
            site_count=12,
            subscriber_count=100,
            session_count=120,
            site_capacity_mbps=600.0,
            simulation_minutes=30.0,
        ),
    )
    scenario.install()
    return scenario


def _command(scenario, profile):
    result = scenario.run_reference_process(profile.workflow_type)
    case = scenario.process_cases[result["case_id"]]
    sensor = next(
        event
        for event in scenario.runtime.journal
        if event.event_id == result["sensor_event_id"]
    )
    command = SimulationCommand(
        command_id=f"cmd-{profile.source_id}",
        trace_id=sensor.trace_id,
        issued_by=profile.function.replace("-", "_"),
        type=profile.command_type,
        payload={
            "case_id": case.id,
            "subject_ids": list(case.subject_ids),
            "action": profile.command_type,
            "skill_outputs": {
                skill: {"reasoning": "deterministic proof"}
                for skill in profile.skills
            },
            "approval_decision": (
                "approve" if profile.hitl_persona else "not_required"
            ),
        },
    )
    return case, command


def test_every_standard_profile_command_mutates_case_and_emits_evidence():
    for index, profile in enumerate(STANDARD_PROCESS_PROFILES.values()):
        scenario = _scenario(80 + index)
        case, command = _command(scenario, profile)

        accepted = scenario.apply_command(command)
        duplicate = scenario.apply_command(command)

        assert accepted.type == "command.accepted"
        assert duplicate is accepted
        assert case.status == "completed"
        assert case.outcome is not None
        success = next(
            event
            for event in scenario.runtime.journal
            if event.type == profile.success_event
            and event.trace_id == command.trace_id
        )
        assert success.actor_id == case.id
        assert success.cause_event_id == accepted.event_id


def test_reference_command_rejects_wrong_action_without_mutation():
    scenario = _scenario(120)
    profile = STANDARD_PROCESS_PROFILES["revenue-assurance"]
    case, command = _command(scenario, profile)
    invalid = SimulationCommand(
        command_id="cmd-invalid",
        trace_id=command.trace_id,
        issued_by=command.issued_by,
        type=profile.command_type,
        payload={**command.payload, "action": "not-declared"},
    )

    result = scenario.apply_command(invalid)

    assert result.type == "command.rejected"
    assert case.status == "open"
    assert case.outcome is None
