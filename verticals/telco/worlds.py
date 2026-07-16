from api.shared.world_contracts import (
    ObjectiveRoute,
    ResponderRegistration,
    WorldPackRegistration,
    WorldScaleProfile,
)


def build_telco_demo(runtime):
    from api.server.world.packs.telco import NetworkConfig, NetworkScenario

    config = NetworkConfig(
        site_count=12,
        subscriber_count=2_000,
        session_count=2_200,
        site_capacity_mbps=600.0,
        simulation_minutes=20_000.0,
    )
    return NetworkScenario(runtime, config)


TELCO_WORLD = WorldPackRegistration(
    name="telco",
    scales={
        "demo": WorldScaleProfile(
            name="demo",
            build_scenario=build_telco_demo,
            default_minutes_per_second=10.0,
        )
    },
    default_scale="demo",
    objective_routes=(
        ObjectiveRoute(
            sensor_id="sensor:network_anomaly",
            objective_type="network_service_recovery",
            allowed_command_types=frozenset({"reroute_sessions"}),
            success_event_types=frozenset({"site.recovered"}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=30.0,
        ),
        ObjectiveRoute(
            sensor_id="sensor:customer_impact",
            objective_type="proactive_customer_care",
            allowed_command_types=frozenset({"apply_customer_remediation"}),
            success_event_types=frozenset({"care.completed"}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=60.0,
        ),
        ObjectiveRoute(
            sensor_id="sensor:service_order",
            objective_type="order_to_activate",
            allowed_command_types=frozenset({"activate_service_order"}),
            success_event_types=frozenset({"order.activated"}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=60.0,
        ),
    ),
    responders={
        "network_service_recovery": ResponderRegistration(
            objective_type="network_service_recovery",
            orchestrator="NetworkIncidentOrchestrator",
            workflow_type="network-incident",
            prefix="incident",
            owner_function="network_incident",
            timeout_seconds=90.0,
            observation_key="incident",
        ),
        "proactive_customer_care": ResponderRegistration(
            objective_type="proactive_customer_care",
            orchestrator="ProactiveCustomerCareOrchestrator",
            workflow_type="proactive-customer-care",
            prefix="care",
            owner_function="customer_care",
            timeout_seconds=900.0,
            observation_key="customer_impact",
        ),
        "order_to_activate": ResponderRegistration(
            objective_type="order_to_activate",
            orchestrator="OrderToActivateOrchestrator",
            workflow_type="order-to-activate",
            prefix="order",
            owner_function="service_fulfillment",
            timeout_seconds=900.0,
            observation_key="service_order",
        ),
    },
)

TELCO_WORLDS = {"telco": TELCO_WORLD}
