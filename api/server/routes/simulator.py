# src/server/routes/simulator.py
from __future__ import annotations
import time as _time

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.server.services.simulator_orchestrator import (
    spawn_expense_workflow, spawn_repeat_offender_ramp, simulate_region_failure,
    spawn_hiring_workflow, spawn_travel_preapproval_workflow,
)
from api.server.state import app_state
from api.shared.events import FleetEvent
from api.shared.types import ActionLedgerEntry

router = APIRouter(prefix="/api/simulator")


class InjectBody(BaseModel):
    scenario: str | None = None


@router.post("/inject")
async def inject(body: InjectBody):
    workflow_id = await spawn_expense_workflow(scenario=body.scenario)
    return {"workflow_id": workflow_id}


class RepeatOffenderBody(BaseModel):
    employee_id: str = Field(default="EMP-0001")
    count: int = Field(default=3, ge=1, le=10)
    delay_seconds: float = Field(default=1.0, ge=0.0, le=10.0)


@router.post("/repeat-offender")
async def repeat_offender(body: RepeatOffenderBody):
    """AC #6 demo trigger: spawn `count` consecutive claims from the
    same employee so the escalation tier visibly ramps."""
    ids = await spawn_repeat_offender_ramp(
        employee_id=body.employee_id,
        count=body.count,
        delay_seconds=body.delay_seconds,
    )
    return {"workflow_ids": ids}


class RegionFailureBody(BaseModel):
    stop_seconds: int = Field(default=10, ge=1, le=120)


@router.post("/region-failure")
async def region_failure(body: RegionFailureBody):
    """Emit a `region.failure.simulated` event marking the wall-clock
    window during which the operator stops the Functions host. Used in
    the AC #11 demo to anchor the audit trail."""
    return await simulate_region_failure(stop_seconds=body.stop_seconds)


class SeedDecisionsBody(BaseModel):
    """AC #7 demo: stamp `count` synthetic reviewer.decision ledger
    entries onto an existing workflow so query_reviewer_decisions
    surfaces a cluster the FM can promote."""
    clause: str = Field(default="§3.1", description="Policy clause id")
    decision: str = Field(default="accept-justification")
    count: int = Field(default=55, ge=1, le=500)
    workflow_id: str | None = Field(
        default=None,
        description=(
            "Target workflow to attach entries to. If omitted, picks the "
            "first in-flight expense-claim workflow."
        ),
    )


@router.post("/seed-decisions")
async def seed_decisions(body: SeedDecisionsBody):
    workflow_id = body.workflow_id
    if not workflow_id:
        for w in app_state.store.list_workflows():
            if w.type == "expense-claim":
                workflow_id = w.id
                break
    if not workflow_id:
        return {"ok": False, "reason": "no expense-claim workflow available"}

    wf = app_state.store.get_workflow(workflow_id)
    if not wf:
        return {"ok": False, "reason": f"workflow {workflow_id!r} not found"}

    now = _time.time()
    for i in range(body.count):
        wf.action_ledger.append(ActionLedgerEntry(
            workflow_id=workflow_id,
            timestamp=now + i * 0.001,
            actor_kind="human",
            actor_id=f"reviewer-{(i % 7) + 1}",
            action="reviewer.decision",
            revocable=False,
            details={
                "recommendation": body.decision,
                "policy_clause": body.clause,
                "category": "meals",
            },
        ))
    return {"ok": True, "workflow_id": workflow_id, "added": body.count}


class HireBody(BaseModel):
    candidate_id: str | None = None
    scenario: str | None = None


@router.post("/hire")
async def inject_hire(body: HireBody):
    """POC2 simulator: spawn a hiring workflow. Optional `candidate_id` picks
    a specific synthetic CV (deterministic). Optional `scenario` tags the
    payload so per-track activities can override behaviour (e.g.
    "rtw-unknown", "betrvg-objection-received")."""
    workflow_id = await spawn_hiring_workflow(
        candidate_id=body.candidate_id, scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}


@router.post("/fleet-tick")
async def fleet_tick():
    """Manually wake the Fleet Manager. Used by the AC #7 demo beat
    after seed-decisions to force the behaviour-change loop to run."""
    app_state.bus.emit(FleetEvent(type="fleet.tick", workflow_id=None))
    return {"ok": True}


# --- Generated-domain entries (compose-domain v1) -------------------------

class TravelBody(BaseModel):
    employee_id: str | None = None
    scenario: str | None = None


@router.post("/travel")
async def inject_travel(body: TravelBody):
    """First generated-domain simulator: spawn a travel pre-approval workflow."""
    workflow_id = await spawn_travel_preapproval_workflow(
        employee_id=body.employee_id, scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}


# === BEGIN compose-domain fleet-employee-onboarding ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_fleet_employee_onboarding_workflow,
)


class FleetEmployeeOnboardingBody(BaseModel):
    employee_id: str | None = None
    department: str | None = None
    scenario: str | None = None


@router.post("/fleet-employee-onboarding")
async def inject_fleet_employee_onboarding(body: FleetEmployeeOnboardingBody):
    """Generated-domain simulator: spawn an Employee onboarding workflow."""
    workflow_id = await spawn_fleet_employee_onboarding_workflow(
        employee_id=body.employee_id,
        department=body.department,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END compose-domain fleet-employee-onboarding ===


# === BEGIN compose-domain fleet-vendor-kyc ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_fleet_vendor_kyc_workflow,
)


class VendorKycBody(BaseModel):
    vendor_name: str | None = None
    country: str | None = None
    proposing_agency: str | None = None
    scenario: str | None = None


@router.post("/fleet-vendor-kyc")
async def inject_fleet_vendor_kyc(body: VendorKycBody):
    """Generated-domain simulator: spawn a Vendor onboarding & KYC workflow."""
    workflow_id = await spawn_fleet_vendor_kyc_workflow(
        vendor_name=body.vendor_name,
        country=body.country,
        proposing_agency=body.proposing_agency,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END compose-domain fleet-vendor-kyc ===


# === BEGIN compose-domain fleet-it-access-request ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_fleet_it_access_request_workflow,
)


class FleetItAccessRequestBody(BaseModel):
    employee_id: str | None = None
    department: str | None = None
    requested_role_templates: list[str] | None = None
    business_justification: str | None = None
    scenario: str | None = None


@router.post("/fleet-it-access-request")
async def inject_fleet_it_access_request(body: FleetItAccessRequestBody):
    """Generated-domain simulator: spawn an IT access request workflow."""
    workflow_id = await spawn_fleet_it_access_request_workflow(
        employee_id=body.employee_id,
        department=body.department,
        requested_role_templates=body.requested_role_templates,
        business_justification=body.business_justification,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END compose-domain fleet-it-access-request ===


# === BEGIN compose-domain fleet-contract-renewal ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_fleet_contract_renewal_workflow,
)


class FleetContractRenewalBody(BaseModel):
    contract_id: str | None = None
    scenario: str | None = None


@router.post("/fleet-contract-renewal")
async def inject_fleet_contract_renewal(body: FleetContractRenewalBody):
    """Generated-domain simulator: spawn a Contract renewal workflow."""
    workflow_id = await spawn_fleet_contract_renewal_workflow(
        contract_id=body.contract_id,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END compose-domain fleet-contract-renewal ===


# === BEGIN compose-domain fleet-perf-review ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_fleet_perf_review_workflow,
)


class FleetPerfReviewBody(BaseModel):
    employee_id: str | None = None
    cycle: str | None = None
    scenario: str | None = None


@router.post("/fleet-perf-review")
async def inject_fleet_perf_review(body: FleetPerfReviewBody):
    """Generated-domain simulator: spawn a Performance review workflow."""
    workflow_id = await spawn_fleet_perf_review_workflow(
        employee_id=body.employee_id,
        cycle=body.cycle,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END compose-domain fleet-perf-review ===


# === BEGIN hand-graduated fleet-ap-invoice ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_fleet_ap_invoice_workflow,
)


class FleetApInvoiceBody(BaseModel):
    invoice_id: str | None = None
    scenario: str | None = None


@router.post("/fleet-ap-invoice")
async def inject_fleet_ap_invoice(body: FleetApInvoiceBody):
    """Hand-graduated domain simulator: spawn an AP invoice workflow."""
    workflow_id = await spawn_fleet_ap_invoice_workflow(
        invoice_id=body.invoice_id,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END hand-graduated fleet-ap-invoice ===


# === BEGIN hand-graduated wave 2: fleet-purchase-order ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_fleet_purchase_order_workflow,
)


class FleetPurchaseOrderBody(BaseModel):
    po_id: str | None = None
    scenario: str | None = None


@router.post("/fleet-purchase-order")
async def inject_fleet_purchase_order(body: FleetPurchaseOrderBody):
    """Hand-graduated domain simulator: spawn a purchase-order workflow."""
    workflow_id = await spawn_fleet_purchase_order_workflow(
        po_id=body.po_id,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END hand-graduated wave 2: fleet-purchase-order ===


# === BEGIN hand-graduated wave 2: fleet-contract-review ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_fleet_contract_review_workflow,
)


class FleetContractReviewBody(BaseModel):
    contract_id: str | None = None
    scenario: str | None = None


@router.post("/fleet-contract-review")
async def inject_fleet_contract_review(body: FleetContractReviewBody):
    """Hand-graduated domain simulator: spawn a contract-review workflow."""
    workflow_id = await spawn_fleet_contract_review_workflow(
        contract_id=body.contract_id,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END hand-graduated wave 2: fleet-contract-review ===


# === BEGIN hand-graduated wave 2: fleet-privacy-dpia ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_fleet_privacy_dpia_workflow,
)


class FleetPrivacyDpiaBody(BaseModel):
    dpia_id: str | None = None
    scenario: str | None = None


@router.post("/fleet-privacy-dpia")
async def inject_fleet_privacy_dpia(body: FleetPrivacyDpiaBody):
    """Hand-graduated domain simulator: spawn a privacy-dpia workflow."""
    workflow_id = await spawn_fleet_privacy_dpia_workflow(
        dpia_id=body.dpia_id,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END hand-graduated wave 2: fleet-privacy-dpia ===


# === BEGIN hand-graduated wave 2: fleet-treasury-fx ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_fleet_treasury_fx_workflow,
)


class FleetTreasuryFxBody(BaseModel):
    op_id: str | None = None
    scenario: str | None = None


@router.post("/fleet-treasury-fx")
async def inject_fleet_treasury_fx(body: FleetTreasuryFxBody):
    """Hand-graduated domain simulator: spawn a treasury-fx workflow."""
    workflow_id = await spawn_fleet_treasury_fx_workflow(
        op_id=body.op_id,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END hand-graduated wave 2: fleet-treasury-fx ===


# === BEGIN POC3: creative-campaign ===
from api.server.services.simulator_orchestrator import (  # noqa: E402
    spawn_creative_campaign_workflow,
)


class CreativeCampaignBody(BaseModel):
    brief_id: str | None = None
    scenario: str | None = None


@router.post("/creative-campaign")
async def inject_creative_campaign(body: CreativeCampaignBody):
    """POC3: spawn a creative-campaign workflow."""
    workflow_id = await spawn_creative_campaign_workflow(
        brief_id=body.brief_id,
        scenario=body.scenario,
    )
    return {"workflow_id": workflow_id}
# === END POC3: creative-campaign ===


# === BEGIN constellation-mode: one-click autonomous-org finale ===
import asyncio  # noqa: E402
import os  # noqa: E402

# Personae that should auto-resolve in Constellation Mode. Mirrors the
# `scripts/profile-everything.sh` profile so the on-screen button reproduces
# what the operator would otherwise have to source-and-restart for.
_CONSTELLATION_PERSONAE = ",".join([
    "line_manager", "claim_submitter", "ssc_reviewer", "finance_bp", "hr_bp",
    "recruiter", "candidate", "onboarding_it_admin", "vendor_kyc_finance_bp",
    "it_access_line_manager", "it_access_it_admin", "contract_finance_bp",
    "contract_line_manager", "perf_review_hr_bp", "perf_review_line_manager",
    "ap_clerk", "controller", "category_manager", "sourcing_lead", "cpo",
    "contracts_counsel", "gc", "dpo", "treasurer", "cfo", "finance_controller",
])


@router.post("/constellation-start")
async def constellation_start():
    """Flip the substrate into the autonomous-org finale state at runtime,
    no restart required.

    Two side effects, both designed to be safe to call repeatedly:

    1. Set ``PERSONA_AUTO_CLOSE`` in the live process env to the full persona
       list. ``persona_responder._auto_close_set()`` reads this var on every
       gate (no caching), so the *next* HITL handoff for any persona in the
       list will auto-resolve. Existing in-flight gates do not retroactively
       close — that's fine, the ramp loop and Constellation seed below
       generate enough fresh workflows to fill the view in seconds.

    2. Spawn one workflow per known domain in parallel so the constellation
       view fills immediately instead of waiting for the steady-state ramp
       (which only spawns from ``SIMULATOR_RAMP_DOMAINS`` — typically
       just expense-claim during the demo). Each spawn uses the same
       infra as the per-domain ``/api/simulator/<domain>`` endpoints, so any
       failure surfaces in the response payload.

    Returns ``{ok, auto_close_count, spawned: [...], failed: [...]}``.
    """
    os.environ["PERSONA_AUTO_CLOSE"] = _CONSTELLATION_PERSONAE

    spawners = [
        ("expense-claim", spawn_expense_workflow()),
        ("hiring", spawn_hiring_workflow()),
        ("travel-preapproval", spawn_travel_preapproval_workflow()),
        ("employee-onboarding", spawn_fleet_employee_onboarding_workflow()),
        ("vendor-kyc", spawn_fleet_vendor_kyc_workflow()),
        ("it-access-request", spawn_fleet_it_access_request_workflow()),
        ("contract-renewal", spawn_fleet_contract_renewal_workflow()),
        ("perf-review", spawn_fleet_perf_review_workflow()),
        ("ap-invoice", spawn_fleet_ap_invoice_workflow()),
        ("purchase-order", spawn_fleet_purchase_order_workflow()),
        ("contract-review", spawn_fleet_contract_review_workflow()),
        ("privacy-dpia", spawn_fleet_privacy_dpia_workflow()),
        ("creative-campaign", spawn_creative_campaign_workflow()),
        ("treasury-fx", spawn_fleet_treasury_fx_workflow()),
    ]
    domains = [d for d, _ in spawners]
    results = await asyncio.gather(
        *[coro for _, coro in spawners], return_exceptions=True,
    )

    spawned: list[dict] = []
    failed: list[dict] = []
    for domain, result in zip(domains, results):
        if isinstance(result, Exception):
            failed.append({"domain": domain, "error": str(result)})
        else:
            spawned.append({"domain": domain, "workflow_id": result})

    return {
        "ok": True,
        "auto_close_count": len(_CONSTELLATION_PERSONAE.split(",")),
        "spawned": spawned,
        "failed": failed,
    }
# === END constellation-mode ===
