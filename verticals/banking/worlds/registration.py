"""Register the Zava Bank world with the substrate.

Only the hero is world-owned. Its sensor opens an objective, the objective
routes to the reimbursement command type, and the responder names the
Durable orchestrator that answers it. The supporting processes are spawned
by the ramp loop instead, so they deliberately have no route here.
"""
from __future__ import annotations

from api.shared.world_contracts import (
    ObjectiveRoute,
    ResponderRegistration,
    WorldPackRegistration,
    WorldScaleProfile,
)
from verticals.banking.fraud_constants import (
    FRAUD_COMMAND_TYPE,
    FRAUD_FAILURE_EVENT,
    FRAUD_FUNCTION,
    FRAUD_OBJECTIVE_TYPE,
    FRAUD_ORCHESTRATOR,
    FRAUD_SENSOR_ID,
    FRAUD_SUCCESS_EVENT,
    FRAUD_WORKFLOW_TYPE,
)
from verticals.banking.worlds.diagnostics import build_diagnostic_input
from verticals.banking.worlds.scenario import ZavaBankWorld


def build_banking_demo(runtime: object) -> ZavaBankWorld:
    world = ZavaBankWorld(seed=runtime.seed, runtime=runtime)
    world.install()
    return world


_ROUTES = (
    ObjectiveRoute(
        sensor_id=FRAUD_SENSOR_ID,
        objective_type=FRAUD_OBJECTIVE_TYPE,
        allowed_command_types=frozenset({FRAUD_COMMAND_TYPE}),
        success_event_types=frozenset({FRAUD_SUCCESS_EVENT}),
        failure_event_types=frozenset({FRAUD_FAILURE_EVENT}),
        evaluation_timeout_minutes=120.0,
    ),
)

_RESPONDERS = {
    FRAUD_OBJECTIVE_TYPE: ResponderRegistration(
        objective_type=FRAUD_OBJECTIVE_TYPE,
        orchestrator=FRAUD_ORCHESTRATOR,
        workflow_type=FRAUD_WORKFLOW_TYPE,
        prefix="bapp",
        owner_function=FRAUD_FUNCTION,
        timeout_seconds=900.0,
        lifecycle_start_via_bridge=True,
    ),
}

_SCALES = {
    "demo": WorldScaleProfile(
        name="demo",
        build_scenario=build_banking_demo,
        default_minutes_per_second=2.0,
    )
}

BANKING_WORLD = WorldPackRegistration(
    name="banking",
    scales=_SCALES,
    default_scale="demo",
    objective_routes=_ROUTES,
    responders=_RESPONDERS,
    build_diagnostic_input=build_diagnostic_input,
)

BANKING_WORLDS = {"banking": BANKING_WORLD}
