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
from verticals.banking.flags import world_screening_enabled
from verticals.banking.support_constants import (
    MULE_COMMAND_TYPE,
    MULE_FUNCTION,
    MULE_OBJECTIVE_TYPE,
    MULE_ORCHESTRATOR,
    MULE_SENSOR_ID,
    MULE_SUCCESS_EVENT,
    MULE_WORKFLOW_TYPE,
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

# With BANKING_WORLD_SCREENING=1 mule investigations are world-owned too: the
# bank's screening trips the mule sensor, and the disposition is applied back
# to the receiving account.
if world_screening_enabled():
    _ROUTES = _ROUTES + (
        ObjectiveRoute(
            sensor_id=MULE_SENSOR_ID,
            objective_type=MULE_OBJECTIVE_TYPE,
            allowed_command_types=frozenset({MULE_COMMAND_TYPE}),
            success_event_types=frozenset({MULE_SUCCESS_EVENT}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=120.0,
        ),
    )
    _RESPONDERS = {
        **_RESPONDERS,
        MULE_OBJECTIVE_TYPE: ResponderRegistration(
            objective_type=MULE_OBJECTIVE_TYPE,
            orchestrator=MULE_ORCHESTRATOR,
            workflow_type=MULE_WORKFLOW_TYPE,
            prefix="bmul",
            owner_function=MULE_FUNCTION,
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
