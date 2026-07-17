from __future__ import annotations

import azure.durable_functions as df

from api.functions.activities.telco_cascade import telco_cascade_decision
from api.functions.activities.telco_profiled import (
    telco_profile_command_activity,
    telco_profile_skill_activity,
)
from api.functions.kernel_registration import create_app
from api.functions.workflows.network_incident import network_incident_orchestration
from api.functions.workflows.network_incident_activities import (
    network_incident_impact_activity,
    network_incident_reroute_activity,
)
from api.functions.workflows.order_to_activate import (
    order_to_activate_orchestration,
)
from api.functions.workflows.order_to_activate_activities import (
    order_activation_feasibility_activity,
    order_activation_prepare_activity,
)
from api.functions.workflows.proactive_customer_care import (
    proactive_customer_care_orchestration,
)
from api.functions.workflows.proactive_customer_care_activities import (
    customer_care_entitlement_activity,
    customer_care_execution_activity,
    customer_care_impact_activity,
)
from api.functions.workflows.telco_cascade import (
    capacity_optimization_orchestration,
    field_repair_dispatch_orchestration,
    outage_risk_management_orchestration,
    predictive_site_maintenance_orchestration,
    retention_orchestration,
    service_ticket_resolution_orchestration,
)
from api.functions.workflows.telco_profiled import (
    telco_assist_recommend_act_orchestration,
    telco_case_triage_resolve_orchestration,
    telco_detect_diagnose_act_orchestration,
    telco_forecast_simulate_plan_orchestration,
    telco_order_fulfil_verify_orchestration,
    telco_risk_investigate_govern_orchestration,
)


app = create_app()


@app.orchestration_trigger(context_name="context")
def NetworkIncidentOrchestrator(context: df.DurableOrchestrationContext):
    return network_incident_orchestration(context)


@app.activity_trigger(input_name="payload")
def network_incident_impact_activity_trigger(payload: dict) -> dict:
    return network_incident_impact_activity(payload)


@app.activity_trigger(input_name="payload")
def network_incident_reroute_activity_trigger(payload: dict) -> dict:
    return network_incident_reroute_activity(payload)


@app.orchestration_trigger(context_name="context")
def ProactiveCustomerCareOrchestrator(context: df.DurableOrchestrationContext):
    return proactive_customer_care_orchestration(context)


@app.activity_trigger(input_name="payload")
def customer_care_impact_activity_trigger(payload: dict) -> dict:
    return customer_care_impact_activity(payload)


@app.activity_trigger(input_name="payload")
def customer_care_entitlement_activity_trigger(payload: dict) -> dict:
    return customer_care_entitlement_activity(payload)


@app.activity_trigger(input_name="payload")
def customer_care_execution_activity_trigger(payload: dict) -> dict:
    return customer_care_execution_activity(payload)


@app.orchestration_trigger(context_name="context")
def OrderToActivateOrchestrator(context: df.DurableOrchestrationContext):
    return order_to_activate_orchestration(context)


@app.activity_trigger(input_name="payload")
def order_activation_feasibility_activity_trigger(payload: dict) -> dict:
    return order_activation_feasibility_activity(payload)


@app.activity_trigger(input_name="payload")
def order_activation_prepare_activity_trigger(payload: dict) -> dict:
    return order_activation_prepare_activity(payload)


@app.orchestration_trigger(context_name="context")
def OutageRiskManagementOrchestrator(context: df.DurableOrchestrationContext):
    return outage_risk_management_orchestration(context)


@app.orchestration_trigger(context_name="context")
def PredictiveSiteMaintenanceOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return predictive_site_maintenance_orchestration(context)


@app.orchestration_trigger(context_name="context")
def FieldRepairDispatchOrchestrator(context: df.DurableOrchestrationContext):
    return field_repair_dispatch_orchestration(context)


@app.orchestration_trigger(context_name="context")
def CapacityOptimizationOrchestrator(context: df.DurableOrchestrationContext):
    return capacity_optimization_orchestration(context)


@app.orchestration_trigger(context_name="context")
def ServiceTicketResolutionOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return service_ticket_resolution_orchestration(context)


@app.orchestration_trigger(context_name="context")
def RetentionOrchestrationOrchestrator(context: df.DurableOrchestrationContext):
    return retention_orchestration(context)


@app.activity_trigger(input_name="payload")
def telco_cascade_decision_activity_trigger(payload: dict) -> dict:
    return telco_cascade_decision(payload)


@app.orchestration_trigger(context_name="context")
def TelcoDetectDiagnoseActOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return telco_detect_diagnose_act_orchestration(context)


@app.orchestration_trigger(context_name="context")
def TelcoForecastSimulatePlanOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return telco_forecast_simulate_plan_orchestration(context)


@app.orchestration_trigger(context_name="context")
def TelcoCaseTriageResolveOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return telco_case_triage_resolve_orchestration(context)


@app.orchestration_trigger(context_name="context")
def TelcoOrderFulfilVerifyOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return telco_order_fulfil_verify_orchestration(context)


@app.orchestration_trigger(context_name="context")
def TelcoRiskInvestigateGovernOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return telco_risk_investigate_govern_orchestration(context)


@app.orchestration_trigger(context_name="context")
def TelcoAssistRecommendActOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return telco_assist_recommend_act_orchestration(context)


@app.activity_trigger(input_name="payload")
def telco_profile_skill_activity_trigger(payload: dict) -> dict:
    return telco_profile_skill_activity(payload)


@app.activity_trigger(input_name="payload")
def telco_profile_command_activity_trigger(payload: dict) -> dict:
    return telco_profile_command_activity(payload)
