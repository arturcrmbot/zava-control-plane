from api.shared.world_contracts import (
    ObjectiveRoute,
    ResponderRegistration,
    WorldPackRegistration,
    WorldScaleProfile,
)


def build_support_demo(runtime):
    from api.server.world.packs.support import SupportConfig, SupportScenario

    config = SupportConfig(
        customer_count=1_000,
        worker_count=40,
        reserve_worker_count=10,
        arrival_rate_per_hour=90,
        simulation_minutes=480,
        sla_minutes=30,
        sensor_backlog_threshold=25,
        sensor_recovery_threshold=10,
    )
    return SupportScenario(runtime, config)


SUPPORT_WORLD = WorldPackRegistration(
    name="support",
    scales={
        "demo": WorldScaleProfile(
            name="demo",
            build_scenario=build_support_demo,
            default_minutes_per_second=10.0,
        )
    },
    default_scale="demo",
    objective_routes=(
        ObjectiveRoute(
            sensor_id="sensor:support_pressure",
            objective_type="support_capacity",
            allowed_command_types=frozenset({"reallocate_workers"}),
            success_event_types=frozenset({"worker.reallocated"}),
            failure_event_types=frozenset({"ticket.abandoned"}),
            evaluation_timeout_minutes=30.0,
        ),
    ),
    responders={
        "support_capacity": ResponderRegistration(
            objective_type="support_capacity",
            orchestrator="SurgeStaffingOrchestrator",
            workflow_type="surge-staffing",
            prefix="surge",
            owner_function="surge_staffing",
            timeout_seconds=90.0,
        )
    },
)

AGENCY_WORLDS = {"support": SUPPORT_WORLD}
