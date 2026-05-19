# function_app.py — Azure Functions v2 programming model entry point.
# Run from repo root via `func start`.
from __future__ import annotations
import azure.functions as func
import azure.durable_functions as df

from api.shared.otel import init_otel
from api.functions.workflows.expense_claim import expense_claim_orchestration
from api.functions.workflows.hiring import hiring_orchestration
from api.functions.workflows.fleet_travel_preapproval import (
    fleet_travel_preapproval_orchestration,
)
from api.functions.workflows.fleet_travel_preapproval_activities import (
    fleet_travel_preapproval_employee_lookup_activity,
    fleet_travel_preapproval_policy_fit_check_activity,
)
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

# Governance kernel — see plan/feature-agent-governance-toolkit-1.md
# (TASK-004). Idempotent module-load init mirroring the FastAPI side. The
# Functions worker shares the same singleton via the in-process module
# global; in dev they are separate processes and so each gets its own
# kernel — that is fine, the kernel is read-mostly and policy is loaded
# from the same source files at boot.
from api.server.services.governance import init_governance
init_governance()


app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# Orchestrator — 7-phase expense claim (POC1)
@app.orchestration_trigger(context_name="context")
def ExpenseClaimOrchestrator(context: df.DurableOrchestrationContext):
    return expense_claim_orchestration(context)


# Orchestrator — 10-phase hiring (POC2 spine; runs alongside POC1 orchestrator)
@app.orchestration_trigger(context_name="context")
def HiringOrchestrator(context: df.DurableOrchestrationContext):
    return hiring_orchestration(context)


# Orchestrator — 3-phase travel pre-approval (first generated domain via compose-domain)
@app.orchestration_trigger(context_name="context")
def FleetTravelPreapprovalOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_travel_preapproval_orchestration(context)


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


# --- Hiring Segment B (Phase 3 of plan/refactor-substrate-agentic-segments-1.md) ---
@app.activity_trigger(input_name="input")
async def hiring_segment_b_activity_trigger(input: dict) -> dict:
    """Run the candidate-discovery agentic segment.

    Replaces job_design + sourcing + triage + screening when
    HIRING_SEGMENT_MODE includes 'b' or 'all'. The orchestrator wraps
    this with a retry loop driven by validate_segment_b_output."""
    from api.functions.segments.hiring_b import run_segment_b
    return await run_segment_b(input)


@app.activity_trigger(input_name="payload")
def validate_segment_b_output_activity_trigger(payload: dict) -> dict:
    """Pydantic validation of the segment's output. Returns
    {ok: True, output} or {ok: False, errors}."""
    from api.functions.segments.hiring_b import SegmentBOutput
    from pydantic import ValidationError
    try:
        validated = SegmentBOutput.model_validate(payload)
        return {"ok": True, "output": validated.model_dump()}
    except ValidationError as e:
        return {"ok": False, "errors": e.errors()}


# --- Hiring Segment D (Phase 4 of plan/refactor-substrate-agentic-segments-1.md) ---
@app.activity_trigger(input_name="input")
async def hiring_segment_d_activity_trigger(input: dict) -> dict:
    from api.functions.segments.hiring_d import run_segment_d
    return await run_segment_d(input)


@app.activity_trigger(input_name="payload")
def validate_segment_d_output_activity_trigger(payload: dict) -> dict:
    from api.functions.segments.hiring_d import SegmentDOutput
    from pydantic import ValidationError
    try:
        return {"ok": True, "output": SegmentDOutput.model_validate(payload).model_dump()}
    except ValidationError as e:
        return {"ok": False, "errors": e.errors()}


# --- Hiring Segment E (Phase 4 of plan/refactor-substrate-agentic-segments-1.md) ---
@app.activity_trigger(input_name="input")
async def hiring_segment_e_activity_trigger(input: dict) -> dict:
    from api.functions.segments.hiring_e import run_segment_e
    return await run_segment_e(input)


@app.activity_trigger(input_name="payload")
def validate_segment_e_output_activity_trigger(payload: dict) -> dict:
    from api.functions.segments.hiring_e import SegmentEOutput
    from pydantic import ValidationError
    try:
        return {"ok": True, "output": SegmentEOutput.model_validate(payload).model_dump()}
    except ValidationError as e:
        return {"ok": False, "errors": e.errors()}


# --- Generated-domain activity triggers (compose-domain v1) ----------------

@app.activity_trigger(input_name="payload")
def fleet_travel_preapproval_employee_lookup_activity_trigger(payload: dict) -> dict:
    return fleet_travel_preapproval_employee_lookup_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_travel_preapproval_policy_fit_check_activity_trigger(payload: dict) -> dict:
    return fleet_travel_preapproval_policy_fit_check_activity(payload)


# HTTP trigger to start a new orchestration. Used by FastAPI's simulator route.
# Endpoint: POST http://localhost:7071/api/orchestrators/ExpenseClaimOrchestrator
@app.route(route="orchestrators/{functionName}")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    function_name = req.route_params.get("functionName")
    payload = req.get_json() if req.get_body() else {}
    instance_id = await client.start_new(function_name, None, payload)
    return client.create_check_status_response(req, instance_id)

# === BEGIN compose-domain fleet-employee-onboarding ===
from api.functions.workflows.fleet_employee_onboarding import (
    fleet_employee_onboarding_orchestration,
)
from api.functions.workflows.fleet_employee_onboarding_activities import (
    fleet_employee_onboarding_employee_lookup_activity,
    fleet_employee_onboarding_access_drafter_activity,
    fleet_employee_onboarding_induction_planner_activity,
)


@app.orchestration_trigger(context_name="context")
def FleetEmployeeOnboardingOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_employee_onboarding_orchestration(context)


@app.activity_trigger(input_name="payload")
def fleet_employee_onboarding_employee_lookup_activity_trigger(payload: dict) -> dict:
    return fleet_employee_onboarding_employee_lookup_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_employee_onboarding_access_drafter_activity_trigger(payload: dict) -> dict:
    return fleet_employee_onboarding_access_drafter_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_employee_onboarding_induction_planner_activity_trigger(payload: dict) -> dict:
    return fleet_employee_onboarding_induction_planner_activity(payload)
# === END compose-domain fleet-employee-onboarding ===

# === BEGIN compose-domain fleet-vendor-kyc ===
from api.functions.workflows.fleet_vendor_kyc import (
    fleet_vendor_kyc_orchestration,
)
from api.functions.workflows.fleet_vendor_kyc_activities import (
    fleet_vendor_kyc_vendor_intake_activity,
    fleet_vendor_kyc_kyc_diligence_activity,
    fleet_vendor_kyc_ubo_resolver_activity,
)


@app.orchestration_trigger(context_name="context")
def FleetVendorKycOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_vendor_kyc_orchestration(context)


@app.activity_trigger(input_name="payload")
def fleet_vendor_kyc_vendor_intake_activity_trigger(payload: dict) -> dict:
    return fleet_vendor_kyc_vendor_intake_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_vendor_kyc_kyc_diligence_activity_trigger(payload: dict) -> dict:
    return fleet_vendor_kyc_kyc_diligence_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_vendor_kyc_ubo_resolver_activity_trigger(payload: dict) -> dict:
    return fleet_vendor_kyc_ubo_resolver_activity(payload)
# === END compose-domain fleet-vendor-kyc ===

# === BEGIN compose-domain fleet-it-access-request ===
from api.functions.workflows.fleet_it_access_request import (
    fleet_it_access_request_orchestration,
)
from api.functions.workflows.fleet_it_access_request_activities import (
    fleet_it_access_request_employee_lookup_activity,
    fleet_it_access_request_rbac_resolver_activity,
    fleet_it_access_request_risk_assessor_activity,
)


@app.orchestration_trigger(context_name="context")
def FleetItAccessRequestOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_it_access_request_orchestration(context)


@app.activity_trigger(input_name="payload")
def fleet_it_access_request_employee_lookup_activity_trigger(payload: dict) -> dict:
    return fleet_it_access_request_employee_lookup_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_it_access_request_rbac_resolver_activity_trigger(payload: dict) -> dict:
    return fleet_it_access_request_rbac_resolver_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_it_access_request_risk_assessor_activity_trigger(payload: dict) -> dict:
    return fleet_it_access_request_risk_assessor_activity(payload)
# === END compose-domain fleet-it-access-request ===

# === BEGIN compose-domain fleet-contract-renewal ===
from api.functions.workflows.fleet_contract_renewal import (
    fleet_contract_renewal_orchestration,
)
from api.functions.workflows.fleet_contract_renewal_activities import (
    fleet_contract_renewal_contract_lookup_activity,
    fleet_contract_renewal_market_benchmarker_activity,
    fleet_contract_renewal_renewal_terms_drafter_activity,
)


@app.orchestration_trigger(context_name="context")
def FleetContractRenewalOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_contract_renewal_orchestration(context)


@app.activity_trigger(input_name="payload")
def fleet_contract_renewal_contract_lookup_activity_trigger(payload: dict) -> dict:
    return fleet_contract_renewal_contract_lookup_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_contract_renewal_market_benchmarker_activity_trigger(payload: dict) -> dict:
    return fleet_contract_renewal_market_benchmarker_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_contract_renewal_renewal_terms_drafter_activity_trigger(payload: dict) -> dict:
    return fleet_contract_renewal_renewal_terms_drafter_activity(payload)
# === END compose-domain fleet-contract-renewal ===

# === BEGIN compose-domain fleet-perf-review ===
from api.functions.workflows.fleet_perf_review import (
    fleet_perf_review_orchestration,
)
from api.functions.workflows.fleet_perf_review_activities import (
    fleet_perf_review_employee_lookup_activity,
    fleet_perf_review_peer_feedback_aggregator_activity,
    fleet_perf_review_calibration_drafter_activity,
)


@app.orchestration_trigger(context_name="context")
def FleetPerfReviewOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_perf_review_orchestration(context)


@app.activity_trigger(input_name="payload")
def fleet_perf_review_employee_lookup_activity_trigger(payload: dict) -> dict:
    return fleet_perf_review_employee_lookup_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_perf_review_peer_feedback_aggregator_activity_trigger(payload: dict) -> dict:
    return fleet_perf_review_peer_feedback_aggregator_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_perf_review_calibration_drafter_activity_trigger(payload: dict) -> dict:
    return fleet_perf_review_calibration_drafter_activity(payload)
# === END compose-domain fleet-perf-review ===

# === BEGIN hand-graduated fleet-ap-invoice ===
from api.functions.workflows.fleet_ap_invoice import (
    fleet_ap_invoice_orchestration,
)
from api.functions.workflows.fleet_ap_invoice_activities import (
    fleet_ap_invoice_invoice_lookup_activity,
    fleet_ap_invoice_three_way_match_activity,
)


@app.orchestration_trigger(context_name="context")
def FleetApInvoiceOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_ap_invoice_orchestration(context)


@app.activity_trigger(input_name="payload")
def fleet_ap_invoice_invoice_lookup_activity_trigger(payload: dict) -> dict:
    return fleet_ap_invoice_invoice_lookup_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_ap_invoice_three_way_match_activity_trigger(payload: dict) -> dict:
    return fleet_ap_invoice_three_way_match_activity(payload)
# === END hand-graduated fleet-ap-invoice ===

# === BEGIN hand-graduated wave 2: fleet-purchase-order ===
from api.functions.workflows.fleet_purchase_order import (
    fleet_purchase_order_orchestration,
)
from api.functions.workflows.fleet_purchase_order_activities import (
    fleet_purchase_order_po_lookup_activity,
    fleet_purchase_order_supplier_check_activity,
    fleet_purchase_order_authority_resolve_activity,
)


@app.orchestration_trigger(context_name="context")
def FleetPurchaseOrderOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_purchase_order_orchestration(context)


@app.activity_trigger(input_name="payload")
def fleet_purchase_order_po_lookup_activity_trigger(payload: dict) -> dict:
    return fleet_purchase_order_po_lookup_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_purchase_order_supplier_check_activity_trigger(payload: dict) -> dict:
    return fleet_purchase_order_supplier_check_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_purchase_order_authority_resolve_activity_trigger(payload: dict) -> dict:
    return fleet_purchase_order_authority_resolve_activity(payload)
# === END hand-graduated wave 2: fleet-purchase-order ===


# === BEGIN hand-graduated wave 2: fleet-contract-review ===
from api.functions.workflows.fleet_contract_review import (
    fleet_contract_review_orchestration,
)
from api.functions.workflows.fleet_contract_review_activities import (
    fleet_contract_review_contract_intake_activity,
    fleet_contract_review_risk_classify_activity,
    fleet_contract_review_authority_resolve_activity,
)


@app.orchestration_trigger(context_name="context")
def FleetContractReviewOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_contract_review_orchestration(context)


@app.activity_trigger(input_name="payload")
def fleet_contract_review_contract_intake_activity_trigger(payload: dict) -> dict:
    return fleet_contract_review_contract_intake_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_contract_review_risk_classify_activity_trigger(payload: dict) -> dict:
    return fleet_contract_review_risk_classify_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_contract_review_authority_resolve_activity_trigger(payload: dict) -> dict:
    return fleet_contract_review_authority_resolve_activity(payload)
# === END hand-graduated wave 2: fleet-contract-review ===


# === BEGIN hand-graduated wave 2: fleet-privacy-dpia ===
from api.functions.workflows.fleet_privacy_dpia import (
    fleet_privacy_dpia_orchestration,
)
from api.functions.workflows.fleet_privacy_dpia_activities import (
    fleet_privacy_dpia_dpia_intake_activity,
    fleet_privacy_dpia_risk_classify_activity,
    fleet_privacy_dpia_authority_resolve_activity,
)


@app.orchestration_trigger(context_name="context")
def FleetPrivacyDpiaOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_privacy_dpia_orchestration(context)


@app.activity_trigger(input_name="payload")
def fleet_privacy_dpia_dpia_intake_activity_trigger(payload: dict) -> dict:
    return fleet_privacy_dpia_dpia_intake_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_privacy_dpia_risk_classify_activity_trigger(payload: dict) -> dict:
    return fleet_privacy_dpia_risk_classify_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_privacy_dpia_authority_resolve_activity_trigger(payload: dict) -> dict:
    return fleet_privacy_dpia_authority_resolve_activity(payload)
# === END hand-graduated wave 2: fleet-privacy-dpia ===


# === BEGIN hand-graduated wave 2: fleet-treasury-fx ===
from api.functions.workflows.fleet_treasury_fx import (
    fleet_treasury_fx_orchestration,
)
from api.functions.workflows.fleet_treasury_fx_activities import (
    fleet_treasury_fx_op_lookup_activity,
    fleet_treasury_fx_position_check_activity,
    fleet_treasury_fx_authority_resolve_activity,
)


@app.orchestration_trigger(context_name="context")
def FleetTreasuryFxOrchestrator(context: df.DurableOrchestrationContext):
    return fleet_treasury_fx_orchestration(context)


@app.activity_trigger(input_name="payload")
def fleet_treasury_fx_op_lookup_activity_trigger(payload: dict) -> dict:
    return fleet_treasury_fx_op_lookup_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_treasury_fx_position_check_activity_trigger(payload: dict) -> dict:
    return fleet_treasury_fx_position_check_activity(payload)


@app.activity_trigger(input_name="payload")
def fleet_treasury_fx_authority_resolve_activity_trigger(payload: dict) -> dict:
    return fleet_treasury_fx_authority_resolve_activity(payload)
# === END hand-graduated wave 2: fleet-treasury-fx ===


# === BEGIN POC3: creative-campaign ===
from api.functions.workflows.creative_campaign import (  # noqa: E402
    creative_campaign_orchestration,
)
from api.functions.workflows.creative_campaign_activities import (  # noqa: E402
    creative_brief_synthesis_activity,
    creative_insight_audience_activity,
    creative_concept_fanout_activity,
    creative_storyboard_render_activity,
    creative_package_handoff_activity,
)


@app.orchestration_trigger(context_name="context")
def CreativeCampaignOrchestrator(context: df.DurableOrchestrationContext):
    return creative_campaign_orchestration(context)


@app.activity_trigger(input_name="payload")
def creative_brief_synthesis_activity_trigger(payload: dict) -> dict:
    return creative_brief_synthesis_activity(payload)


@app.activity_trigger(input_name="payload")
def creative_insight_audience_activity_trigger(payload: dict) -> dict:
    return creative_insight_audience_activity(payload)


@app.activity_trigger(input_name="payload")
def creative_concept_fanout_activity_trigger(payload: dict) -> dict:
    return creative_concept_fanout_activity(payload)


@app.activity_trigger(input_name="payload")
def creative_storyboard_render_activity_trigger(payload: dict) -> dict:
    return creative_storyboard_render_activity(payload)


@app.activity_trigger(input_name="payload")
def creative_package_handoff_activity_trigger(payload: dict) -> dict:
    return creative_package_handoff_activity(payload)
# === END POC3: creative-campaign ===


# === BEGIN pitch-c1: minimal pass-through orchestrators for promoted stubs ===
# pitch-c1, c2 and c3 graduate ~22 strategic / meta / agency-specific
# domains whose phases are deterministic and exist primarily to populate
# the entity graph. The orchestrators below are minimal pass-through
# stubs that emit a workflow.completed checkpoint and return — no real
# work happens in the orchestrator itself; the substrate captures the
# spawn + projection. Real graduation lands in a later phase.
def _strategic_stub_orchestration(context: df.DurableOrchestrationContext, *, domain: str):
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id,
        "instance_id": context.instance_id,
        "kind": "workflow.completed",
        "payload": {"domain": domain, "status": "stub-completed"},
    })
    return {"status": "completed", "domain": domain}


@app.orchestration_trigger(context_name="context")
def HireToProductiveOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="hire-to-productive")


@app.orchestration_trigger(context_name="context")
def VendorRiskToPayOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="vendor-risk-to-pay")


@app.orchestration_trigger(context_name="context")
def LeadToCashOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="lead-to-cash")


@app.orchestration_trigger(context_name="context")
def FyCloseOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="fy-close")


@app.orchestration_trigger(context_name="context")
def BoardPrepOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="board-prep")
# === END pitch-c1: minimal pass-through orchestrators ===


# === BEGIN pitch-c2: meta-workflow pass-through orchestrators ===
@app.orchestration_trigger(context_name="context")
def MediaPitchToWinOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="media-pitch-to-win")


@app.orchestration_trigger(context_name="context")
def AccountOnboardingOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="account-onboarding")


@app.orchestration_trigger(context_name="context")
def IntercompanyRechargeOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="intercompany-recharge")


@app.orchestration_trigger(context_name="context")
def TalentRedeploymentOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="talent-redeployment")


@app.orchestration_trigger(context_name="context")
def AgencyNetworkRollUpOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="agency-network-roll-up")


@app.orchestration_trigger(context_name="context")
def MAndAIntegrationOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="m-and-a-integration")


@app.orchestration_trigger(context_name="context")
def CrisisResponseOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="crisis-response")
# === END pitch-c2: meta-workflow pass-through orchestrators ===


# === BEGIN pitch-c3: agency-specific pass-through orchestrators ===
@app.orchestration_trigger(context_name="context")
def CreativeAwardsSubmissionOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="creative-awards-submission")


@app.orchestration_trigger(context_name="context")
def ClientRenewalOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="client-renewal")


@app.orchestration_trigger(context_name="context")
def FreelancerOnboardingOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="freelancer-onboarding")


@app.orchestration_trigger(context_name="context")
def DataCleanRoomSetupOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="data-clean-room-setup")


@app.orchestration_trigger(context_name="context")
def WeeklyPitchReviewOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="weekly-pitch-review")


@app.orchestration_trigger(context_name="context")
def MonthlyClientPnlOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="monthly-client-pnl")


@app.orchestration_trigger(context_name="context")
def QuarterlyCreativeAwardsOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="quarterly-creative-awards")


@app.orchestration_trigger(context_name="context")
def AnnualBudgetSettingOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="annual-budget-setting")


@app.orchestration_trigger(context_name="context")
def NewBusinessPipelineScrubOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="new-business-pipeline-scrub")


@app.orchestration_trigger(context_name="context")
def IntercompanyTalentTransferOrchestrator(context: df.DurableOrchestrationContext):
    return _strategic_stub_orchestration(context, domain="intercompany-talent-transfer")
# === END pitch-c3: agency-specific pass-through orchestrators ===
