# function_app.py — Azure Functions v2 programming model entry point.
# Run from repo root via `func start`.
from __future__ import annotations
import azure.functions as func
import azure.durable_functions as df

from api.shared.otel import init_otel
from api.functions.workflows.invoice_p2p import invoice_p2p_orchestration
from api.functions.workflows.activities import (
    intake_activity, validation_activity, routing_activity, approval_activity,
    payment_activity, reconciliation_activity, checkpoint_activity,
)

# Wire OTEL at worker module-load; DF orchestrator + activity spans export to Foundry.
init_otel("control-plane-functions")


app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# Orchestrator registration
@app.orchestration_trigger(context_name="context")
def InvoiceP2POrchestrator(context: df.DurableOrchestrationContext):
    return invoice_p2p_orchestration(context)


# Activity registrations — Azure DF requires each as a decorated function in function_app.py
@app.activity_trigger(input_name="payload")
def intake_activity_trigger(payload: dict) -> dict:
    return intake_activity(payload)


@app.activity_trigger(input_name="payload")
def validation_activity_trigger(payload: dict) -> dict:
    return validation_activity(payload)


@app.activity_trigger(input_name="payload")
def routing_activity_trigger(payload: dict) -> dict:
    return routing_activity(payload)


@app.activity_trigger(input_name="payload")
def approval_activity_trigger(payload: dict) -> dict:
    return approval_activity(payload)


@app.activity_trigger(input_name="payload")
def payment_activity_trigger(payload: dict) -> dict:
    return payment_activity(payload)


@app.activity_trigger(input_name="payload")
def reconciliation_activity_trigger(payload: dict) -> dict:
    return reconciliation_activity(payload)


@app.activity_trigger(input_name="payload")
def checkpoint_activity_trigger(payload: dict) -> dict:
    return checkpoint_activity(payload)


# HTTP trigger that starts a new orchestration (used by FastAPI's simulator route via Phase 10's HTTP starter).
# Endpoint: POST http://localhost:7071/api/orchestrators/InvoiceP2POrchestrator
@app.route(route="orchestrators/{functionName}")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    function_name = req.route_params.get("functionName")
    payload = req.get_json() if req.get_body() else {}
    instance_id = await client.start_new(function_name, None, payload)
    return client.create_check_status_response(req, instance_id)
