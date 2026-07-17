from api.shared.world_contracts import (
    ObjectiveRoute,
    ResponderRegistration,
    WorldPackRegistration,
    WorldScaleProfile,
)
from verticals.telco.domains import ENGINE_ORCHESTRATORS
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES


def build_telco_demo(runtime):
    from verticals.telco.world import NetworkConfig, NetworkScenario

    config = NetworkConfig(
        site_count=12,
        subscriber_count=2_000,
        session_count=2_200,
        site_capacity_mbps=600.0,
        simulation_minutes=20_000.0,
    )
    return NetworkScenario(runtime, config)


STANDARD_OBJECTIVE_ROUTES = tuple(
    ObjectiveRoute(
        sensor_id=profile.sensor_id,
        objective_type=profile.objective_type,
        allowed_command_types=frozenset({profile.command_type}),
        success_event_types=frozenset({profile.success_event}),
        failure_event_types=frozenset({"command.rejected"}),
        evaluation_timeout_minutes=120.0,
    )
    for profile in STANDARD_PROCESS_PROFILES.values()
)
STANDARD_RESPONDERS = {
    profile.objective_type: ResponderRegistration(
        objective_type=profile.objective_type,
        orchestrator=ENGINE_ORCHESTRATORS[profile.engine],
        workflow_type=profile.workflow_type,
        prefix=profile.source_id.lower().replace("-", ""),
        owner_function=profile.function.replace("-", "_"),
        timeout_seconds=900.0,
        observation_key="process_case",
    )
    for profile in STANDARD_PROCESS_PROFILES.values()
}


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
        ObjectiveRoute(
            sensor_id="sensor:outage_risk",
            objective_type="outage_prevention",
            allowed_command_types=frozenset({"prestage_field_resources"}),
            success_event_types=frozenset({"resources.prestaged"}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=60.0,
        ),
        ObjectiveRoute(
            sensor_id="sensor:asset_failure_risk",
            objective_type="site_maintenance",
            allowed_command_types=frozenset({"create_maintenance_work_order"}),
            success_event_types=frozenset({"work_order.created"}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=120.0,
        ),
        ObjectiveRoute(
            sensor_id="sensor:work_order_ready",
            objective_type="field_repair",
            allowed_command_types=frozenset({"dispatch_field_repair"}),
            success_event_types=frozenset({"asset.repaired", "asset.replaced"}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=180.0,
        ),
        ObjectiveRoute(
            sensor_id="sensor:site_congestion",
            objective_type="capacity_recovery",
            allowed_command_types=frozenset({"apply_capacity_action"}),
            success_event_types=frozenset({"site.capacity.stable"}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=120.0,
        ),
        ObjectiveRoute(
            sensor_id="sensor:ticket_pressure",
            objective_type="ticket_resolution",
            allowed_command_types=frozenset({"resolve_ticket_batch"}),
            success_event_types=frozenset({"ticket_batch.resolved"}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=180.0,
        ),
        ObjectiveRoute(
            sensor_id="sensor:churn_risk",
            objective_type="customer_retention",
            allowed_command_types=frozenset({"apply_retention_offer"}),
            success_event_types=frozenset({"retention_offer.issued"}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=240.0,
        ),
        *STANDARD_OBJECTIVE_ROUTES,
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
        "outage_prevention": ResponderRegistration(
            objective_type="outage_prevention",
            orchestrator="OutageRiskManagementOrchestrator",
            workflow_type="outage-risk-management",
            prefix="outage",
            owner_function="network_operations",
            timeout_seconds=900.0,
            observation_key="weather_risk",
        ),
        "site_maintenance": ResponderRegistration(
            objective_type="site_maintenance",
            orchestrator="PredictiveSiteMaintenanceOrchestrator",
            workflow_type="predictive-site-maintenance",
            prefix="maintenance",
            owner_function="network_operations",
            timeout_seconds=900.0,
            observation_key="asset_failure_risk",
        ),
        "field_repair": ResponderRegistration(
            objective_type="field_repair",
            orchestrator="FieldRepairDispatchOrchestrator",
            workflow_type="field-repair-dispatch",
            prefix="field",
            owner_function="network_operations",
            timeout_seconds=900.0,
            observation_key="work_order",
        ),
        "capacity_recovery": ResponderRegistration(
            objective_type="capacity_recovery",
            orchestrator="CapacityOptimizationOrchestrator",
            workflow_type="capacity-optimization",
            prefix="capacity",
            owner_function="network_operations",
            timeout_seconds=900.0,
            observation_key="site_congestion",
        ),
        "ticket_resolution": ResponderRegistration(
            objective_type="ticket_resolution",
            orchestrator="ServiceTicketResolutionOrchestrator",
            workflow_type="service-ticket-resolution",
            prefix="ticket",
            owner_function="customer_care",
            timeout_seconds=900.0,
            observation_key="ticket_pressure",
        ),
        "customer_retention": ResponderRegistration(
            objective_type="customer_retention",
            orchestrator="RetentionOrchestrationOrchestrator",
            workflow_type="retention-orchestration",
            prefix="retention",
            owner_function="customer_care",
            timeout_seconds=900.0,
            observation_key="churn_risk",
        ),
        **STANDARD_RESPONDERS,
    },
)

TELCO_WORLDS = {"telco": TELCO_WORLD}
