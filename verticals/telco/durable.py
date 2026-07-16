from __future__ import annotations

import azure.durable_functions as df

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
