# function_app.py — Azure Functions v2 programming model entry point.
# Run from repo root via `func start`.
from __future__ import annotations
import azure.functions as func
import azure.durable_functions as df

from api.shared.otel import init_otel
from api.functions.workflows.expense_claim import expense_claim_orchestration
from api.functions.workflows.hiring import hiring_orchestration
from api.functions.workflows.activities import (
    intake_activity,
    classify_activity,
    receipt_activity,
    route_activity,
    notify_activity,
    arbitrate_activity,
    audit_activity,
    checkpoint_activity,
    # POC2 hiring spine
    hiring_budget_activity,
    hiring_job_design_activity,
    hiring_sourcing_activity,
    hiring_triage_activity,
    hiring_screening_activity,
    hiring_voice_activity,
    issue_screen_link_activity,
    send_screen_email_activity,
    hiring_compliance_activity,
    hiring_offer_activity,
    hiring_onboarding_activity,
    hiring_interview_recommender_activity,
    issue_book_interview_link_activity,
    send_book_interview_email_activity,
    send_rejection_email_activity,
)

# Wire OTEL at worker module-load; DF orchestrator + activity spans export to Foundry.
init_otel("control-plane-functions")


app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# Orchestrator — 7-phase expense claim (POC1)
@app.orchestration_trigger(context_name="context")
def ExpenseClaimOrchestrator(context: df.DurableOrchestrationContext):
    return expense_claim_orchestration(context)


# Orchestrator — 10-phase hiring (POC2 spine; runs alongside POC1 orchestrator)
@app.orchestration_trigger(context_name="context")
def HiringOrchestrator(context: df.DurableOrchestrationContext):
    return hiring_orchestration(context)


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


@app.activity_trigger(input_name="payload")
def checkpoint_activity_trigger(payload: dict) -> dict:
    return checkpoint_activity(payload)


# --- POC2 hiring activity triggers ---------------------------------------

@app.activity_trigger(input_name="payload")
def hiring_budget_activity_trigger(payload: dict) -> dict:
    return hiring_budget_activity(payload)


@app.activity_trigger(input_name="payload")
def hiring_job_design_activity_trigger(payload: dict) -> dict:
    return hiring_job_design_activity(payload)


@app.activity_trigger(input_name="payload")
def hiring_sourcing_activity_trigger(payload: dict) -> dict:
    return hiring_sourcing_activity(payload)


@app.activity_trigger(input_name="payload")
def hiring_triage_activity_trigger(payload: dict) -> dict:
    return hiring_triage_activity(payload)


@app.activity_trigger(input_name="payload")
def hiring_screening_activity_trigger(payload: dict) -> dict:
    return hiring_screening_activity(payload)


@app.activity_trigger(input_name="payload")
def hiring_voice_activity_trigger(payload: dict) -> dict:
    return hiring_voice_activity(payload)


# Phase 6 voice screen — magic-link issuance + email delivery happen as
# their own activities so they show up as discrete spans on the workflow
# timeline. The orchestration generator suspends on `voice_complete`
# between these and the FastAPI /transcript callback.
@app.activity_trigger(input_name="payload")
def issue_screen_link_activity_trigger(payload: dict) -> dict:
    return issue_screen_link_activity(payload)


@app.activity_trigger(input_name="payload")
def send_screen_email_activity_trigger(payload: dict) -> dict:
    return send_screen_email_activity(payload)


@app.activity_trigger(input_name="payload")
def hiring_interview_recommender_activity_trigger(payload: dict) -> dict:
    return hiring_interview_recommender_activity(payload)


@app.activity_trigger(input_name="payload")
def issue_book_interview_link_activity_trigger(payload: dict) -> dict:
    return issue_book_interview_link_activity(payload)


@app.activity_trigger(input_name="payload")
def send_book_interview_email_activity_trigger(payload: dict) -> dict:
    return send_book_interview_email_activity(payload)


@app.activity_trigger(input_name="payload")
def send_rejection_email_activity_trigger(payload: dict) -> dict:
    return send_rejection_email_activity(payload)


@app.activity_trigger(input_name="payload")
def hiring_compliance_activity_trigger(payload: dict) -> dict:
    return hiring_compliance_activity(payload)


@app.activity_trigger(input_name="payload")
def hiring_offer_activity_trigger(payload: dict) -> dict:
    return hiring_offer_activity(payload)


@app.activity_trigger(input_name="payload")
def hiring_onboarding_activity_trigger(payload: dict) -> dict:
    return hiring_onboarding_activity(payload)


# HTTP trigger to start a new orchestration. Used by FastAPI's simulator route.
# Endpoint: POST http://localhost:7071/api/orchestrators/ExpenseClaimOrchestrator
@app.route(route="orchestrators/{functionName}")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    function_name = req.route_params.get("functionName")
    payload = req.get_json() if req.get_body() else {}
    instance_id = await client.start_new(function_name, None, payload)
    return client.create_check_status_response(req, instance_id)
