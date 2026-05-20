# src/server/routes/simulator.py
from __future__ import annotations
import random as _random
import string as _string
import time as _time

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
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
    # Escalation parents: required so deterministic cascades (OOO,
    # three-way-match failures, escalate-up-hierarchy) land on auto-closing
    # personae instead of stalling the demo. Discovered when ap_clerk's
    # AP-001/002 escalations and finance_bp's OOO cascade for HIRE Budget
    # both stalled on bp_pod_lead — see persona_responder._escalation_parent.
    "bp_pod_lead", "regional_controller_emea",
    "regional_hr_lead", "hr_director",
    "account_director",
    # Gate-owning personae for creative-* / crisis-response /
    # data-clean-room-setup. All terminal in the hierarchy (no escalation
    # parent), so they need to be in the auto-close set directly to keep
    # creative-campaign brief_capture + 4 other CD gates, ops_signoff and
    # data_signoff flowing in Constellation Mode.
    "creative_director", "change_manager", "chief_data_officer",
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


@router.post("/dream-storm")
async def dream_storm(
    domains: str = "hiring",
    runs: int = 3,
    sample: int = 10,
):
    """Fire ``runs`` dream passes per domain in ``domains`` (comma-separated)
    back-to-back. Demo-only: lets the operator fill the Memory page
    timeline in seconds rather than waiting for the autonomous cadence.

    Unknown domains do not 500 — they emit an ``error`` row in the
    response so a partial multi-domain storm still completes.
    """
    from api.server.services.dream_pass.skill_loader import (
        DreamSkillLoadError, dream_skill_path, load_dream_skill,
    )
    from api.server.routes.dream_pass_pause import is_paused as _is_paused
    dom_list = [d.strip() for d in domains.split(",") if d.strip()]
    passes: list[dict] = []
    for dom in dom_list:
        if _is_paused(dom):
            passes.append({"domain": dom, "error": "paused (kill switch)"})
            continue
        if app_state.cost_budget.is_over_budget(dom):
            passes.append({"domain": dom, "error": "budget (daily LLM cost exceeded)"})
            continue
        try:
            skill = load_dream_skill(dream_skill_path(dom))
        except (DreamSkillLoadError, FileNotFoundError) as ex:
            passes.append({"domain": dom, "error": str(ex)})
            continue
        for _ in range(max(1, int(runs))):
            result = await app_state.dream_pass_orchestrator.run_pass(
                skill=skill, sample_size=sample,
            )
            passes.append({
                "dream_pass_id": result.dream_pass_id,
                "domain": result.domain,
                "promoted": len(result.promoted_lesson_ids),
                "rejected": len(result.rejected_lesson_ids),
                "flagged": len(result.flagged_lesson_ids),
                "experiments_run": len(result.experiments),
            })
    return {"ok": True, "count": len(passes), "passes": passes}


# Ralph-loop helper — seed every function FM's KPIs with synthetic
# values so the building's KPI tickers read as populated for the
# demo / smoke. Idempotent. Safe to call repeatedly.
@router.post("/seed-kpis")
async def seed_kpis():
    import random as _rnd
    from api.shared.functions import FUNCTIONS

    fm_registry = getattr(app_state, "function_fms", None)
    if not fm_registry:
        return {"ok": False, "reason": "function_fms not initialised"}

    period = _time.strftime("%Y-%m")
    seeded: list[dict] = []
    for fn_key, fn_spec in FUNCTIONS.items():
        if fn_key == "legacy" or not fn_spec.kpis:
            continue
        fm = fm_registry.get(fn_key)
        if fm is None:
            continue
        for metric in fn_spec.kpis:
            # Pseudo-random but deterministic per (fn, metric) so reseeds
            # don't churn the building's KPI tickers wildly.
            rng = _rnd.Random(f"{fn_key}:{metric}")
            base = rng.uniform(10, 95)
            value = round(base + rng.uniform(-2.0, 2.0), 1)
            try:
                fm.publish_kpi(metric, value, period)
                seeded.append({"function": fn_key, "metric": metric,
                               "value": value, "period": period})
            except Exception as exc:  # noqa: BLE001
                seeded.append({"function": fn_key, "metric": metric,
                               "error": str(exc)})
    return {"ok": True, "count": len(seeded), "seeded": seeded[:20]}


# ---------------------------------------------------------------------------
# Org Ops v2 — burst injector for the operator views' "spawn 5" button.
# Picks a varied selection of workflows so the live stream / conversations /
# river immediately show activity across multiple functions, not just one.
# ---------------------------------------------------------------------------
@router.post("/inject-burst")
async def inject_burst(n: int = 5):
    """Spawn ~n varied workflows across multiple domains.

    Used by the Org Ops v2 page top-right "burst" button so an operator can
    pump activity at will. Distributes across finance / hr / ops / legal /
    marketing so all three views get cross-function content. Returns a list
    of spawned workflow_ids.
    """
    import asyncio
    from api.server.services.simulator_orchestrator import (  # noqa: E402
        spawn_fleet_vendor_kyc_workflow,
        spawn_fleet_ap_invoice_workflow,
        spawn_fleet_perf_review_workflow,
        spawn_fleet_treasury_fx_workflow,
        spawn_fleet_contract_renewal_workflow,
        spawn_fleet_employee_onboarding_workflow,
        spawn_fleet_it_access_request_workflow,
        spawn_fleet_purchase_order_workflow,
        spawn_creative_campaign_workflow,
        spawn_hiring_workflow,
    )
    n = max(1, min(int(n or 5), 20))
    spawners = [
        ("vendor-kyc", spawn_fleet_vendor_kyc_workflow()),
        ("ap-invoice", spawn_fleet_ap_invoice_workflow()),
        ("perf-review", spawn_fleet_perf_review_workflow()),
        ("hiring", spawn_hiring_workflow()),
        ("treasury-fx", spawn_fleet_treasury_fx_workflow()),
        ("creative-campaign", spawn_creative_campaign_workflow()),
        ("contract-renewal", spawn_fleet_contract_renewal_workflow()),
        ("employee-onboarding", spawn_fleet_employee_onboarding_workflow()),
        ("it-access-request", spawn_fleet_it_access_request_workflow()),
        ("purchase-order", spawn_fleet_purchase_order_workflow()),
    ]
    selected = spawners[:n]
    results = await asyncio.gather(
        *[coro for _, coro in selected], return_exceptions=True,
    )
    spawned: list[dict] = []
    for (domain, _), result in zip(selected, results):
        if isinstance(result, Exception):
            spawned.append({"domain": domain, "error": str(result)})
        else:
            spawned.append({"domain": domain, "workflow_id": result})
    return {"ok": True, "count": len(spawned), "spawned": spawned}


# === BEGIN pitch-h7: crisis injection (client-loss wow moment) ===
class CrisisClientLossBody(BaseModel):
    """Body for the `/crisis/client-loss` wow-moment trigger."""
    client_id: str = Field(..., description="Entity id of the client (e.g. ORG-client-soylent-group)")
    reason: str = Field(default="", description="Free-text rationale for the loss event")


# The 4 simultaneous workflows the wow-moment fires across the org.
# Each entry: (workflow_type, payload_key, payload_extras_builder).
# Kept here (not in DOMAINS) so the storm definition is one-grep visible.
_CRISIS_WORKFLOW_TYPES: tuple[str, ...] = (
    "contract-review",
    "talent-redeployment",
    "intercompany-recharge",
    "board-prep",
)


def _crisis_random_suffix() -> str:
    """4-char uppercase alphanumeric suffix for crisis-spawned workflow ids."""
    alphabet = _string.ascii_uppercase + _string.digits
    return "".join(_random.choice(alphabet) for _ in range(4))


def _crisis_affected_subsidiaries(client_id: str) -> list[str]:
    """Best-effort lookup: subsidiaries that executed campaigns for this client.

    Returns ``[]`` if the entity graph isn't wired or the query fails — the
    crisis injection is a demo trigger, not a financial calculation, so we
    surface what we can without making the endpoint brittle.
    """
    entities = getattr(app_state, "entities", None)
    if entities is None:
        return []
    try:
        rows = entities.query(
            "MATCH (s:Subsidiary)<-[:EXECUTED_BY]-(:Campaign)"
            "-[:CAMPAIGN_FOR]->(:Brand)-[:BRAND_OF]->(o:Organisation {id: $cid}) "
            "RETURN DISTINCT s.id AS id",
            {"cid": client_id},
        )
    except Exception:
        return []
    out: list[str] = []
    for row in rows:
        sid = row.get("id") if isinstance(row, dict) else None
        if isinstance(sid, str) and sid not in out:
            out.append(sid)
    return out


def _build_crisis_workflow(
    *,
    workflow_id: str,
    workflow_type: str,
    payload: dict,
) -> "_Workflow":
    from api.shared.types import Workflow as _Workflow
    now = _time.time()
    return _Workflow(
        id=workflow_id,
        type=workflow_type,
        current_phase="Intake",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava",
        payload=payload,
    )


@router.post("/crisis/client-loss", status_code=status.HTTP_202_ACCEPTED)
async def crisis_client_loss(body: CrisisClientLossBody):
    """pitch-h7 wow-moment: a key client wants out.

    Single-call event that drops 4 simultaneous workflows across the org so
    the demo has a visible "storm" — contract-review (offboarding),
    talent-redeployment (affected staff), intercompany-recharge (reverse
    unwind) and board-prep (loss entry).

    Behaviour:
    1. 404 if the client entity id is unknown.
    2. 500 if any of the 4 target domains is missing from the registry.
    3. Emits ONE ``crisis.injected`` FleetEvent before the spawns so the
       cosmic lens can render a shockwave effect.
    4. Audit-logs the injection with all 4 spawned workflow ids.
    5. Returns 202 with ``{spawned_workflow_ids: [...]}``.
    """
    from api.shared.domains import DOMAINS
    from api.shared.events import FleetEvent

    # 1. Client must exist.
    entities = getattr(app_state, "entities", None)
    if entities is None or entities.get(body.client_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"client {body.client_id!r} not found",
        )

    # 2. All 4 target domains must be registered (post c1+c2+c3).
    for wf_type in _CRISIS_WORKFLOW_TYPES:
        if wf_type not in DOMAINS:
            raise HTTPException(
                status_code=500,
                detail=f"crisis target domain missing from registry: {wf_type!r}",
            )

    affected = _crisis_affected_subsidiaries(body.client_id)

    # Pre-mint ids so we can include them in the shockwave + audit entry.
    spawned_ids: list[str] = []
    plans: list[tuple[str, str, dict]] = []  # (wf_id, wf_type, payload)
    for wf_type in _CRISIS_WORKFLOW_TYPES:
        prefix = DOMAINS[wf_type].workflow_id_prefix
        wid = f"{prefix}-{_crisis_random_suffix()}"
        spawned_ids.append(wid)
        if wf_type == "contract-review":
            payload = {
                "purpose": "offboarding",
                "client_id": body.client_id,
                "reason": body.reason,
            }
        elif wf_type == "talent-redeployment":
            payload = {
                "client_id": body.client_id,
                "affected_subsidiaries": affected,
                "reason": body.reason,
            }
        elif wf_type == "intercompany-recharge":
            payload = {
                "direction": "reverse",
                "client_id": body.client_id,
                "reason": body.reason,
            }
        else:  # board-prep
            payload = {
                "kind": "client_loss",
                "client_id": body.client_id,
                "reason": body.reason,
            }
        plans.append((wid, wf_type, payload))

    # 3. Shockwave first so the lens animation precedes the storm.
    try:
        app_state.bus.emit(FleetEvent(
            type="crisis.injected",
            workflow_id=None,
            client_id=body.client_id,
            reason=body.reason,
            spawned_workflow_ids=list(spawned_ids),
        ))
    except Exception as ex:
        print(f"[crisis] failed to emit crisis.injected: {ex}")

    # 4. Spawn the 4 workflows + emit per-workflow workflow.started.
    for wid, wf_type, payload in plans:
        w = _build_crisis_workflow(
            workflow_id=wid, workflow_type=wf_type, payload=payload,
        )
        app_state.store.upsert_workflow(w)
        try:
            app_state.bus.emit(FleetEvent(
                type="workflow.started",
                workflow_id=wid,
                workflow_type=wf_type,
                crisis=True,
                client_id=body.client_id,
            ))
        except Exception as ex:
            print(f"[crisis] failed to emit workflow.started for {wid}: {ex}")

    # 5. Audit ledger entry — one row, all four ids attached.
    try:
        app_state.audit.log("crisis.injected", {
            "client_id": body.client_id,
            "reason": body.reason,
            "spawned_workflow_ids": list(spawned_ids),
        })
    except Exception as ex:
        print(f"[crisis] failed to audit-log crisis.injected: {ex}")

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"spawned_workflow_ids": spawned_ids},
    )
# === END pitch-h7: crisis injection ===
