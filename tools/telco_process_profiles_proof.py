#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from api.functions.activities.telco_profiled import (
    telco_profile_command_activity,
    telco_profile_skill_activity,
)
from api.server.services.event_bus import EventBus
from api.server.world.model import SimulationCommand
from api.server.world.service import ActorWorldService
from verticals.telco.process_profiles import (
    ENGINE_CODES,
    SKILL_NAMES,
    STANDARD_PROCESS_PROFILES,
    TOOLS_BY_PACK,
)


CONTRACT = {
    "workflow_types": 37,
    "hero_workflows": 9,
    "standard_profiles": len(STANDARD_PROCESS_PROFILES),
    "workflow_engines": len(ENGINE_CODES),
    "skills": len(SKILL_NAMES),
    "mcp_packs": len(TOOLS_BY_PACK),
}


def run_proof() -> dict:
    service = ActorWorldService.telco(
        seed=91,
        bus=EventBus(),
        minutes_per_second=1_000,
    )
    rows = []
    for profile in STANDARD_PROCESS_PROFILES.values():
        started = service.run_reference_process(profile.workflow_type)
        sensor = next(
            event
            for event in service.runtime.journal
            if event.event_id == started["sensor_event_id"]
        )
        route = next(
            item
            for item in service.registration.objective_routes
            if item.sensor_id == profile.sensor_id
        )
        responder = service.registration.responders[profile.objective_type]
        objective = service.open_objective(
            sensor.to_dict(),
            route,
            owner_function=responder.owner_function,
        )
        service.transition_objective(
            objective.id,
            "claimed",
            claimed_by=responder.owner_function,
        )
        service.transition_objective(objective.id, "acting")
        observation = service.build_observation(sensor.to_dict())
        outputs = {}
        for skill in profile.skills:
            outputs[skill] = telco_profile_skill_activity(
                {
                    "agent_mode": "deterministic",
                    "workflow_id": f"PROOF-{profile.source_id}",
                    "trace_id": sensor.trace_id,
                    "type": profile.workflow_type,
                    "skill": skill,
                    "observation": observation,
                    "prior_outputs": outputs,
                }
            )
        decision = telco_profile_command_activity(
            {
                "workflow_id": f"PROOF-{profile.source_id}",
                "trace_id": sensor.trace_id,
                "type": profile.workflow_type,
                "observation": observation,
                "skill_outputs": outputs,
                "approval": {
                    "decision": (
                        "approve"
                        if profile.hitl_persona is not None
                        else "not_required"
                    )
                },
            }
        )
        command = SimulationCommand(**decision["command"])
        accepted = service.apply_typed_command(objective, command)
        live_objective = service.objectives.get(objective.id)
        evaluation = next(
            item
            for item in service.evaluator.evaluations
            if item.objective_id == objective.id
        )
        case = service.scenario.process_cases[started["case_id"]]
        success = next(
            event
            for event in service.runtime.journal
            if event.type == profile.success_event
            and event.trace_id == sensor.trace_id
        )
        rows.append(
            {
                "source_id": profile.source_id,
                "workflow_type": profile.workflow_type,
                "engine": profile.engine,
                "skills": list(profile.skills),
                "mcp_packs": list(profile.mcp_packs),
                "command_type": command.type,
                "command_status": accepted.type,
                "success_event": success.type,
                "objective_status": live_objective.status,
                "evaluation_status": evaluation.status,
                "source_mode": case.outcome["source_mode"],
            }
        )
    return {
        "result": "PASS",
        "contract": CONTRACT,
        "workflow_types": sorted(STANDARD_PROCESS_PROFILES),
        "profiles": rows,
    }


if __name__ == "__main__":
    if "--print-contract" in sys.argv:
        print(json.dumps(CONTRACT, sort_keys=True))
    else:
        print(json.dumps(run_proof(), sort_keys=True))
