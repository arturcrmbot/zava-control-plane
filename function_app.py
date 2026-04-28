# function_app.py — Azure Functions v2 programming model entry point.
# Run from repo root via `func start`.
from __future__ import annotations
import azure.functions as func
import azure.durable_functions as df

from api.shared.otel import init_otel
from api.functions.workflows.expense_claim import expense_claim_orchestration
from api.functions.workflows.activities import (
    intake_activity,
    classify_activity,
    receipt_activity,
    route_activity,
    notify_activity,
    arbitrate_activity,
    audit_activity,
    approval_activity,
    checkpoint_activity,
)

# Wire OTEL at worker module-load; DF orchestrator + activity spans export to Foundry.
init_otel("control-plane-functions")


app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# Orchestrator — 7-phase expense claim
@app.orchestration_trigger(context_name="context")
def ExpenseClaimOrchestrator(context: df.DurableOrchestrationContext):
    return expense_claim_orchestration(context)


# Deprecated invoice orchestrator — kept registered as a no-op so any
# in-flight Durable history rows from before the Week 2 pivot can rehydrate
# and complete cleanly instead of failing on replay. Returns a deprecation
# marker on first activation. Remove after the storage account has been
# confirmed clean of invoice-p2p instances.
@app.orchestration_trigger(context_name="context")
def InvoiceP2POrchestrator(context: df.DurableOrchestrationContext):
    return _invoice_p2p_deprecated(context)


def _invoice_p2p_deprecated(context: df.DurableOrchestrationContext):
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": (context.get_input() or {}).get("workflow_id", "?"),
        "instance_id": context.instance_id,
        "kind": "workflow.completed",
        "payload": {"status": "deprecated", "note": "InvoiceP2POrchestrator retired in Week 2 pivot"},
    })
    return {"status": "deprecated", "phase": "Sunset"}


# Activity registrations — Azure DF requires each as a decorated function in function_app.py
@app.activity_trigger(input_name="payload")
def intake_activity_trigger(payload: dict) -> dict:
    return intake_activity(payload)


@app.activity_trigger(input_name="payload")
def classify_activity_trigger(payload: dict) -> dict:
    return classify_activity(payload)


@app.activity_trigger(input_name="payload")
def receipt_activity_trigger(payload: dict) -> dict:
    return receipt_activity(payload)


@app.activity_trigger(input_name="payload")
def route_activity_trigger(payload: dict) -> dict:
    return route_activity(payload)


@app.activity_trigger(input_name="payload")
def notify_activity_trigger(payload: dict) -> dict:
    return notify_activity(payload)


@app.activity_trigger(input_name="payload")
def arbitrate_activity_trigger(payload: dict) -> dict:
    return arbitrate_activity(payload)


@app.activity_trigger(input_name="payload")
def audit_activity_trigger(payload: dict) -> dict:
    return audit_activity(payload)


# Approval activity retained for any in-flight invoice-p2p orchestrators (none in steady state).
@app.activity_trigger(input_name="payload")
def approval_activity_trigger(payload: dict) -> dict:
    return approval_activity(payload)


@app.activity_trigger(input_name="payload")
def checkpoint_activity_trigger(payload: dict) -> dict:
    return checkpoint_activity(payload)


# HTTP trigger to start a new orchestration. Used by FastAPI's simulator route.
# Endpoint: POST http://localhost:7071/api/orchestrators/ExpenseClaimOrchestrator
@app.route(route="orchestrators/{functionName}")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    function_name = req.route_params.get("functionName")
    payload = req.get_json() if req.get_body() else {}
    instance_id = await client.start_new(function_name, None, payload)
    return client.create_check_status_response(req, instance_id)
