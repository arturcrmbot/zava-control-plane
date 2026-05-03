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
