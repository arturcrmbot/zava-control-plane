"""api/shared/domains.py — Domain registry: single source of truth.

Every per-domain integration fact (workflow_type, prefix, orchestrator name,
HITL gates, persona, external_event, operator surface, optional wake hints)
lives in `DOMAINS` keyed by workflow_type. Adding a 9th domain via
`compose-domain` becomes one entry here.

Consumers:
- api.server.services.simulator_orchestrator — spawner dispatch
- api.server.services.blueprint_inventory   — visual mind-map composition
- api.server.routes.workflows               — workflow_id-prefix → workflow_type
- api.server.routes.exceptions              — current_phase → external_event fallback
- api.server.services.triage                — wake-event allow-list extension
- api.server.services.fleet_manager_service — domain catalogue inside FM skill
- api.shared.functions — derives Domain.function back-ref at import; orphan validator runs at boot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PhaseKind = Literal["deterministic", "agent", "hitl"]


@dataclass(frozen=True)
class Phase:
    """A workflow phase — used for documentation + FM skill text generation.

    `name` matches the human-readable step name fired via `step.started`
    by `_run_workflow` in api/functions/workflows/activities.py. HITL
    phases that are pure orchestrator yields (no activity wrapper) carry
    the snake_case gate name to match the suspended-payload `phase` field.
    """
    name: str
    kind: PhaseKind


@dataclass(frozen=True)
class HitlGate:
    """A HITL suspend point on a domain's workflow.

    The orchestrator stamps `phase` (snake_case for fleet domains, mixed
    for POC1/POC2) on every suspended payload; the responder + resolve
    route use that key to find the matching `external_event`. The
    `persona` matches a SKILL.md role under api/server/personae/.
    """
    gate_phase: str
    external_event: str
    persona: str
    # Probability per gate hit that the persona declines to auto-resolve
    # and the gate stays open for a human (or surfaces as an FM exception).
    # 0.0 = always auto-close (legacy behaviour); 1.0 = always wait.
    # Sensible per-gate values calibrated by risk profile in DOMAINS below.
    wait_probability: float = 0.0
    # Pitch-c6: long-tail HITL personae. Each roll is independent and
    # checked in order (sick → holiday → override → timeout); the FIRST
    # one that hits wins, then the rest are skipped for that gate hit.
    # Defaults are 0.0 so all existing HitlGate(...) call-sites keep
    # working unchanged. Hand-set 0.05–0.15 on a tactical handful of
    # gates so the demo isn't homogeneous.
    sick_probability: float = 0.0       # persona is sick today; cascade to delegate (parent)
    holiday_probability: float = 0.0    # persona is on holiday; cascade to delegate (parent)
    timeout_probability: float = 0.0    # auto-escalate after timeout; emits workflow.hitl.timeout
    override_probability: float = 0.0   # persona overrides policy (rare; demos defiance)


@dataclass(frozen=True)
class RegionOverlay:
    """Per-region overrides layered on top of a base ``Domain``.

    Pitch-c4: most jurisdictions reuse the canonical phase set, but a
    handful add region-specific compliance phases (DE works council, JP
    stamp tax, US monthly cycle, etc.) or tighten policy thresholds.
    Hand-authored for a small set of (domain, region) pairs; everything
    else falls back to the base phases unchanged.

    The orchestrator does NOT consume overlays today — this is
    registry-only metadata. Persona prompts and the HUD will read it via
    ``Domain.phases_for_region`` once those surfaces light up.
    """
    extra_phases: tuple["Phase", ...] = ()
    policy_threshold_overrides: dict[str, float] = field(default_factory=dict)
    extra_hitl_gates: tuple["HitlGate", ...] = ()


@dataclass(frozen=True)
class WakeHint:
    """Domain-specific event the FM should treat as wake-worthy.

    These are anticipatory signals (e.g. POC1's `claim.routed.red`) the
    FM should react to before a HITL gate trips. Declared per domain in
    the registry; only fires when the domain's activities/validators
    actually emit the event.
    """
    event: str
    reason: str


@dataclass
class Domain:
    workflow_type: str
    display_name: str
    workflow_id_prefix: str
    orchestrator_name: str
    operator_surface: str
    phases: tuple[Phase, ...]
    hitl_gates: tuple[HitlGate, ...]
    skills: tuple[str, ...]
    wake_hints: tuple[WakeHint, ...] = ()
    # `function` is mutated exactly once at import time by
    # api.shared.functions._wire_function_back_refs(); treat as
    # immutable thereafter. The dataclass is non-frozen *only* to
    # accommodate this single boot-time back-ref write.
    function: str | None = None
    # Phase 4 IP5+6 (TASK-027/028). When True, this Domain is a stub
    # for a meta-workflow / strategic CEO domain that is registered in
    # the org-clone surface as a graduation placeholder but is NOT
    # spawned at runtime — it has no orchestrator file and no
    # ``spawn_fn``. The orphan validator and FM-skill catalog still
    # see the entry; orchestrator-name resolution tests skip it. Use
    # ``live_domains()`` below to filter stubs out of runtime contexts.
    stub: bool = False
    # Phase: realistic_interval_seconds + spawn_fn + wait_probability
    # ---------------------------------------------------------------
    # `spawn_fn` is the dotted path of the simulator coroutine that spawns
    # one workflow of this type. ``_resolve_spawner(domain)`` in
    # api/server/services/simulator_orchestrator.py imports + caches the
    # callable. None for stubs (they have no spawner). Required for live
    # domains; the orphan validator at boot (api/shared/functions.py)
    # ensures coverage.
    spawn_fn: str | None = None
    # Realistic real-world spawn cadence in seconds (e.g. AP invoice every
    # 1800s = 30 min). Effective demo cadence = realistic_interval_seconds
    # / DEMO_TIME_WARP_FACTOR (default 60). None falls back to the legacy
    # SIMULATOR_RAMP_AVG_INTERVAL_SECONDS env var.
    realistic_interval_seconds: int | None = None
    # Pitch-c4: optional per-region overlays keyed by ISO-ish region code
    # (e.g. "DE", "US", "JP"). Empty for most domains; a handful of
    # (domain, region) pairs are hand-authored to demonstrate that the
    # substrate can carry regional compliance variants without cloning
    # the entire Domain definition. See ``phases_for_region``.
    region_overlays: dict[str, RegionOverlay] = field(default_factory=dict)
    # Pitch-c5: long-cycle domains (contracts, perf reviews, M&A,
    # annual budgets, …) where wall-clock cadence is unrealistic. The
    # simulator stretches their effective spawn interval and stamps
    # ``created_at`` with business-time so dashboards age them
    # plausibly during a fast-forward demo.
    slow_burn: bool = False

    def phases_for_region(self, region: str | None) -> tuple[Phase, ...]:
        """Return base phases plus any region-overlay extras.

        Unknown / missing region codes fall back to the base phase tuple
        unchanged so callers can pass any value safely. Overlay extras
        are appended *after* the base phases (regional gates today are
        always additional compliance steps near the end of the flow).
        """
        if not region:
            return self.phases
        overlay = self.region_overlays.get(region)
        if overlay is None or not overlay.extra_phases:
            return self.phases
        return self.phases + tuple(overlay.extra_phases)


# --------------------------------------------------------------------------
# The registry. Entries grouped by graduation order (POC1 expense first,
# POC2 hiring second, then the six fleet-* domains generated by
# compose-domain v3 over the 2026-05 weekend).
# --------------------------------------------------------------------------

DOMAINS: dict[str, Domain] = {
    # ----- POC1 -----
    "expense-claim": Domain(
        workflow_type="expense-claim",
        display_name="Finance Compliance",
        workflow_id_prefix="EXP",
        orchestrator_name="ExpenseClaimOrchestrator",
        operator_surface="finance-controller",
        phases=(
            Phase("Intake", "deterministic"),
            Phase("Classify", "agent"),
            Phase("Validate Receipt", "agent"),
            Phase("Route", "agent"),
            Phase("Notify", "hitl"),
            Phase("Arbitrate", "hitl"),
            Phase("Audit", "agent"),
        ),
        hitl_gates=(
            HitlGate("Notify", "justification", "claim_submitter", wait_probability=0.05),
            HitlGate("Arbitrate", "reviewer_decision", "ssc_reviewer", wait_probability=0.3),
        ),
        skills=(
            "field-extractor", "line-item-extractor", "rag-classifier",
            "receipt-validator", "escalation-advisor", "notification-composer",
            "arbitration", "anomaly-flagger", "exception-classifier",
            "resolution-recommender", "root-cause-explainer", "audit-summariser",
            "use-document-intelligence",
        ),
        wake_hints=(
            WakeHint("claim.routed.red", "Red verdict before HITL gate trips"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_expense_workflow",
        realistic_interval_seconds=2700,
        # Pitch-c4: DE adds a Works-Council notification step + tighter
        # auto-approval threshold; US adds a monthly-cycle close phase.
        region_overlays={
            "DE": RegionOverlay(
                extra_phases=(Phase("Works-Council Notify", "deterministic"),),
                policy_threshold_overrides={"auto_approve_max_eur": 250.0},
            ),
            "US": RegionOverlay(
                extra_phases=(Phase("Monthly Cycle Close", "deterministic"),),
                policy_threshold_overrides={"monthly_cycle_close_day": 25.0},
            ),
        },
    ),
    # ----- POC2 -----
    "hiring": Domain(
        workflow_type="hiring",
        display_name="Hiring",
        workflow_id_prefix="HIRE",
        orchestrator_name="HiringOrchestrator",
        operator_surface="hr-bp",
        phases=(
            Phase("Budget", "hitl"),
            Phase("Job Design", "agent"),
            Phase("Sourcing", "agent"),
            Phase("Triage", "agent"),
            Phase("Screening", "agent"),
            Phase("Voice", "hitl"),
            Phase("Interview", "hitl"),
            Phase("Compliance", "agent"),
            Phase("Offer", "hitl"),
            Phase("Onboarding", "agent"),
        ),
        hitl_gates=(
            HitlGate("Budget", "budget_approval", "finance_bp", wait_probability=0.1),
            HitlGate("Voice", "voice_complete", "candidate", wait_probability=0.05),
            HitlGate("Interview", "interview_invite", "recruiter", wait_probability=0.15,
                     override_probability=0.10),
            HitlGate("Offer", "offer_approval", "candidate", wait_probability=0.2),
        ),
        skills=(
            "budget-checker", "jd-drafter", "sourcing-orchestrator",
            "cv-crystalliser", "auto-shortlister", "voice-screener",
            "interview-recommender", "interview-coordinator",
            "jurisdiction-router", "betrvg-checker", "offer-personaliser",
            "exception-classifier", "use-document-intelligence",
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_hiring_workflow",
        realistic_interval_seconds=86400,
    ),
    # ----- Weekend fleet-* domains (compose-domain v3) -----
    "travel-preapproval": Domain(
        workflow_type="travel-preapproval",
        display_name="Travel pre-approval",
        workflow_id_prefix="TRV",
        orchestrator_name="FleetTravelPreapprovalOrchestrator",
        operator_surface="line-manager",
        phases=(
            Phase("Employee Lookup", "deterministic"),
            Phase("Policy Fit Check", "agent"),
            Phase("manager_approval", "hitl"),
        ),
        hitl_gates=(
            HitlGate("manager_approval", "manager_approval_decision", "line_manager",
                     wait_probability=0.1, sick_probability=0.10, holiday_probability=0.05),
        ),
        skills=(
            "fleet-travel-preapproval-policy-fit-checker",
        ),
        wake_hints=(
            WakeHint("travel.policy.exception", "Trip outside policy band before approval"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_travel_preapproval_workflow",
        realistic_interval_seconds=7200,
    ),
    "vendor-kyc": Domain(
        workflow_type="vendor-kyc",
        display_name="Vendor onboarding & KYC",
        workflow_id_prefix="VKY",
        orchestrator_name="FleetVendorKycOrchestrator",
        operator_surface="finance-bp",
        phases=(
            Phase("Vendor Intake", "deterministic"),
            Phase("KYC Diligence", "agent"),
            Phase("UBO Resolver", "agent"),
            Phase("finance_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("finance_signoff", "finance_signoff_decision", "vendor_kyc_finance_bp", wait_probability=0.2),
        ),
        skills=(
            "fleet-vendor-kyc-kyc-diligence-checker",
            "fleet-vendor-kyc-ubo-resolver",
        ),
        wake_hints=(
            WakeHint("vendor.kyc.high_risk", "Vendor in high-risk jurisdiction or sanctions hit"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_vendor_kyc_workflow",
        realistic_interval_seconds=43200,
        # Pitch-c4: DE-domiciled vendors require a BaFin filing step.
        region_overlays={
            "DE": RegionOverlay(
                extra_phases=(Phase("BaFin Filing", "deterministic"),),
            ),
        },
    ),
    "employee-onboarding": Domain(
        workflow_type="employee-onboarding",
        display_name="Employee onboarding",
        workflow_id_prefix="ONB",
        orchestrator_name="FleetEmployeeOnboardingOrchestrator",
        operator_surface="it-admin",
        phases=(
            Phase("Employee Lookup", "deterministic"),
            Phase("Access Drafter", "agent"),
            Phase("it_admin_approval", "hitl"),
            Phase("Induction Planner", "agent"),
        ),
        hitl_gates=(
            HitlGate("it_admin_approval", "it_admin_approval_decision", "onboarding_it_admin", wait_probability=0.05),
        ),
        skills=(
            "fleet-employee-onboarding-access-drafter",
            "fleet-employee-onboarding-induction-planner",
        ),
        wake_hints=(
            WakeHint("onboarding.access.broad_scope", "Joiner requesting broad access scope"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_employee_onboarding_workflow",
        realistic_interval_seconds=86400,
    ),
    "employee-transfer": Domain(
        workflow_type="employee-transfer",
        display_name="Employee transfer between organisations",
        workflow_id_prefix="EMT",
        orchestrator_name="FleetEmployeeTransferOrchestrator",
        operator_surface="hr-bp",
        phases=(
            Phase("Transfer Intake", "deterministic"),
            Phase("Employee Lookup", "deterministic"),
            Phase("Eligibility Check", "agent"),
            Phase("manager_approval", "hitl"),
            Phase("Compensation Remap", "agent"),
            Phase("hr_director_signoff", "hitl"),
            Phase("Identity Migration", "deterministic"),
        ),
        hitl_gates=(
            HitlGate("manager_approval", "manager_approval_decision",
                     "line_manager", wait_probability=0.1),
            HitlGate("hr_director_signoff", "hr_director_decision",
                     "hr_director", wait_probability=0.25),
        ),
        skills=(
            "fleet-employee-transfer-transfer-eligibility-checker",
            "fleet-employee-transfer-compensation-remapper",
        ),
        wake_hints=(
            WakeHint("hr.transfer.cross_border", "Cross-border transfer requires visa/work-permit review"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_employee_transfer_workflow",
        realistic_interval_seconds=21600,
    ),
    "it-access-request": Domain(
        workflow_type="it-access-request",
        display_name="IT access request",
        workflow_id_prefix="ITAR",
        orchestrator_name="FleetItAccessRequestOrchestrator",
        operator_surface="it-admin",
        phases=(
            Phase("Employee Lookup", "deterministic"),
            Phase("RBAC Resolver", "agent"),
            Phase("Risk Assessor", "agent"),
            Phase("line_manager_approval", "hitl"),
            Phase("it_admin_approval", "hitl"),
        ),
        hitl_gates=(
            HitlGate("line_manager_approval", "line_manager_approval_decision",
                     "it_access_line_manager", wait_probability=0.1),
            HitlGate("it_admin_approval", "it_admin_approval_decision",
                     "it_access_it_admin", wait_probability=0.15),
        ),
        skills=(
            "fleet-it-access-request-rbac-resolver",
            "fleet-it-access-request-access-risk-assessor",
        ),
        wake_hints=(
            WakeHint("access.scope.privileged", "Privileged-tier role template requested"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_it_access_request_workflow",
        realistic_interval_seconds=14400,
    ),
    "contract-renewal": Domain(
        workflow_type="contract-renewal",
        display_name="Contract renewal",
        workflow_id_prefix="CRN",
        orchestrator_name="FleetContractRenewalOrchestrator",
        operator_surface="finance-bp",
        phases=(
            Phase("Contract Lookup", "deterministic"),
            Phase("Market Benchmarker", "agent"),
            Phase("Renewal Terms Drafter", "agent"),
            Phase("finance_signoff", "hitl"),
            Phase("contract_owner_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("finance_signoff", "finance_signoff_decision", "contract_finance_bp", wait_probability=0.2),
            HitlGate("contract_owner_signoff", "contract_owner_signoff_decision",
                     "contract_line_manager", wait_probability=0.15),
        ),
        skills=(
            "fleet-contract-renewal-market-benchmarker",
            "fleet-contract-renewal-renewal-terms-drafter",
        ),
        wake_hints=(
            WakeHint("contract.renewal.price_jump", "Proposed value >25% above current"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_contract_renewal_workflow",
        realistic_interval_seconds=259200,
        slow_burn=True,
        # Pitch-c4: JP contracts require Stamp-Tax validation.
        region_overlays={
            "JP": RegionOverlay(
                extra_phases=(Phase("Stamp-Tax Validate", "deterministic"),),
            ),
        },
    ),
    "perf-review": Domain(
        workflow_type="perf-review",
        display_name="Performance review",
        workflow_id_prefix="PRR",
        orchestrator_name="FleetPerfReviewOrchestrator",
        operator_surface="hr-bp",
        phases=(
            Phase("Employee Lookup", "deterministic"),
            Phase("Peer Feedback Aggregator", "agent"),
            Phase("Calibration Drafter", "agent"),
            Phase("hr_calibration", "hitl"),
            Phase("line_manager_delivery", "hitl"),
        ),
        hitl_gates=(
            HitlGate("hr_calibration", "hr_calibration_decision", "perf_review_hr_bp", wait_probability=0.25),
            HitlGate("line_manager_delivery", "line_manager_delivery_decision",
                     "perf_review_line_manager", wait_probability=0.1),
        ),
        skills=(
            "fleet-perf-review-peer-feedback-aggregator",
            "fleet-perf-review-calibration-drafter",
        ),
        wake_hints=(
            WakeHint("perf.calibration.outlier", "Calibration draft is a >2-band outlier"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_perf_review_workflow",
        realistic_interval_seconds=5184000,
        slow_burn=True,
    ),
    # ----- Hand-graduated: AP invoice (9th live domain) -----
    # Proves the curve: once the substrate primitives (authority MCP +
    # persona registry + compose-persona) are in place, the next domain
    # reuses them without per-persona engineering. ap_clerk + controller
    # personae are unchanged from Phase 6 graduation — they decide gates
    # against AP-001..AP-004 in the matrix.
    "ap-invoice": Domain(
        workflow_type="ap-invoice",
        display_name="AP invoice",
        workflow_id_prefix="API",
        orchestrator_name="FleetApInvoiceOrchestrator",
        operator_surface="ap-clerk",
        phases=(
            Phase("Invoice Lookup", "deterministic"),
            Phase("Three-Way Match", "deterministic"),
            Phase("ap_clerk_signoff", "hitl"),
            Phase("controller_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("ap_clerk_signoff", "ap_invoice_processing_decision", "ap_clerk",
                     wait_probability=0.05, sick_probability=0.05, timeout_probability=0.10),
            HitlGate("controller_signoff", "controller_signoff_decision", "controller",
                     wait_probability=0.2, holiday_probability=0.05),
        ),
        skills=(
            # Deterministic phases — no agent skills today.
            # Engagement-POC graduation adds a real LLM-driven line-item validator.
        ),
        wake_hints=(
            WakeHint("invoice.three_way_match.failed", "Invoice failed three-way match"),
            WakeHint("invoice.value.controller_band", "Invoice >£25k routed to controller"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_ap_invoice_workflow",
        realistic_interval_seconds=1800,
    ),

    # ----- Hand-graduated wave 2 (10th–13th live domains) -----
    # All four use a 4-phase pattern:
    #   Phase 1 deterministic lookup -> Phase 2 deterministic check ->
    #   Phase 3 Authority Resolve (calls matrix MCP, picks approver_role
    #   dynamically) -> Phase 4 HITL approver_signoff. The HitlGate
    #   persona below is the *most-likely* / lowest-band approver; the
    #   actual responder uses the resolved approver_role from the
    #   suspended payload's persona field, so any of the matrix-routed
    #   roles can take the gate.
    "purchase-order": Domain(
        workflow_type="purchase-order",
        display_name="Purchase Order",
        workflow_id_prefix="POW",
        orchestrator_name="FleetPurchaseOrderOrchestrator",
        operator_surface="procurement",
        phases=(
            Phase("PO Lookup", "deterministic"),
            Phase("Supplier Check", "deterministic"),
            Phase("Authority Resolve", "deterministic"),
            Phase("approver_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("approver_signoff", "purchase_order_approval_decision", "line_manager", wait_probability=0.15),
        ),
        skills=(),
        wake_hints=(
            WakeHint("po.supplier.unapproved", "PO supplier not on approved list"),
            WakeHint("po.value.cpo_band", "PO >£500k routed to CPO"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_purchase_order_workflow",
        realistic_interval_seconds=21600,
    ),
    "contract-review": Domain(
        workflow_type="contract-review",
        display_name="Contract Review",
        workflow_id_prefix="CRW",
        orchestrator_name="FleetContractReviewOrchestrator",
        operator_surface="legal",
        phases=(
            Phase("Contract Intake", "deterministic"),
            Phase("Risk Classify", "deterministic"),
            Phase("Authority Resolve", "deterministic"),
            Phase("approver_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("approver_signoff", "contract_review_signoff_decision", "contracts_counsel", wait_probability=0.3),
        ),
        skills=(),
        wake_hints=(
            WakeHint("contract.template.deviation", "Contract deviates from template"),
            WakeHint("contract.value.material", "Contract MSA >£250k routed to GC"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_contract_review_workflow",
        realistic_interval_seconds=172800,
        slow_burn=True,
    ),
    "privacy-dpia": Domain(
        workflow_type="privacy-dpia",
        display_name="Privacy DPIA",
        workflow_id_prefix="DPI",
        orchestrator_name="FleetPrivacyDpiaOrchestrator",
        operator_surface="privacy",
        phases=(
            Phase("DPIA Intake", "deterministic"),
            Phase("Risk Classify", "deterministic"),
            Phase("Authority Resolve", "deterministic"),
            Phase("approver_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("approver_signoff", "dpia_signoff_decision", "dpo", wait_probability=0.4),
        ),
        skills=(),
        wake_hints=(
            WakeHint("dpia.risk.high", "DPIA flagged as high-risk processing"),
            WakeHint("dpia.gdpr.art_35", "EMEA high-risk DPIA — GDPR Art. 35 trigger"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_privacy_dpia_workflow",
        realistic_interval_seconds=432000,
    ),
    "treasury-fx": Domain(
        workflow_type="treasury-fx",
        display_name="Treasury FX",
        workflow_id_prefix="TFX",
        orchestrator_name="FleetTreasuryFxOrchestrator",
        operator_surface="treasury",
        phases=(
            Phase("Op Lookup", "deterministic"),
            Phase("Position Check", "deterministic"),
            Phase("Authority Resolve", "deterministic"),
            Phase("approver_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("approver_signoff", "treasury_signoff_decision", "treasurer", wait_probability=0.3),
        ),
        skills=(),
        wake_hints=(
            WakeHint("fx.position.over_limit", "FX op exceeds per-pair trading limit"),
            WakeHint("fx.value.cfo_band", "FX op >£1M routed to CFO"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fleet_treasury_fx_workflow",
        realistic_interval_seconds=86400,
    ),

    # ----- POC3 — Creative Campaign (AI-Agency demo) -----
    # Per plan/feature-poc3-ai-agency-1.md. The four storyboard-defined HITL
    # gates (◆1 brief approval, ◆2 concept lock, ◆3 storyboard approval,
    # ◆4 final signoff) plus the Phase-1 voice intake (parks waiting for the
    # creative director to complete the multi-party briefing call) are all
    # five entries below. Phase 1 ships every phase as a stub against canned
    # image fixtures under data/synthetic/creative-campaign/cached/; Phases
    # 2–4 swap stubs for real Foundry gpt-image-2 + brand-RAG.
    "creative-campaign": Domain(
        workflow_type="creative-campaign",
        display_name="Creative Campaign",
        workflow_id_prefix="CMP",
        orchestrator_name="CreativeCampaignOrchestrator",
        operator_surface="producer-queue",
        phases=(
            Phase("brief_capture", "hitl"),
            Phase("Brief Synthesis", "agent"),
            Phase("brief_approval", "hitl"),
            Phase("Insight & Audience", "agent"),
            Phase("Concept Fan-out", "agent"),
            Phase("concept_lock", "hitl"),
            Phase("Storyboard Render", "agent"),
            Phase("storyboard_approval", "hitl"),
            Phase("final_signoff", "hitl"),
            Phase("Package & Handoff", "agent"),
        ),
        hitl_gates=(
            HitlGate("brief_capture", "voice_complete", "creative_director", wait_probability=0.05),
            HitlGate("brief_approval", "brief_approval_decision", "creative_director", wait_probability=0.1),
            HitlGate("concept_lock", "concept_lock_decision", "creative_director", wait_probability=0.1),
            HitlGate("storyboard_approval", "storyboard_approval_decision",
                     "creative_director", wait_probability=0.15),
            HitlGate("final_signoff", "final_signoff_decision", "creative_director", wait_probability=0.2),
        ),
        skills=(
            "creative-briefer",
            "brief-synthesiser",
            "concept-curator",
            "brand-guardian",
            "storyboard-curator",
        ),
        wake_hints=(
            WakeHint("creative.content_safety.rejected",
                     "gpt-image-2 RAI filter rejected a render"),
            WakeHint("creative.brand.distinctiveness_low",
                     "Concept route scored below distinctiveness threshold"),
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_creative_campaign_workflow",
        realistic_interval_seconds=604800,
    ),
    # --------------------------------------------------------------
    # Phase 4 IP5+6 — meta-workflow + CEO strategic stubs (TASK-027,
    # TASK-028). These are graduated via compose-domain v4 from briefs
    # under docs/superpowers/specs/. Their orchestrators live as
    # rendered-string codegen output (validated by ast.parse, NOT
    # written to api/functions/workflows/ in this phase). The stubs
    # below exist purely to satisfy the orphan validator in
    # api.shared.functions: every domain a function claims must be in
    # DOMAINS, and every domain in DOMAINS must be claimed.
    # --------------------------------------------------------------
    # ----- pitch-c1: promote five strategic stubs to live domains. -----
    # Phases stay deterministic so we don't need real LLM tool wiring;
    # they exist primarily to populate the entity graph and exercise the
    # substrate end-to-end.
    "hire-to-productive": Domain(
        workflow_type="hire-to-productive",
        display_name="Hire to Productive",
        workflow_id_prefix="H2P",
        orchestrator_name="HireToProductiveOrchestrator",
        operator_surface="hr-bp",
        phases=(
            Phase("Joiner Intake", "deterministic"),
            Phase("Onboarding Plan", "deterministic"),
            Phase("Productivity Check", "deterministic"),
            Phase("manager_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("manager_signoff", "manager_onboarding_plan_decision",
                     "hr_bp", wait_probability=0.15),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_hire_to_productive_workflow",
        realistic_interval_seconds=604800,
    ),
    "vendor-risk-to-pay": Domain(
        workflow_type="vendor-risk-to-pay",
        display_name="Vendor Risk to Pay",
        workflow_id_prefix="VRP",
        orchestrator_name="VendorRiskToPayOrchestrator",
        operator_surface="finance-controller",
        phases=(
            Phase("Vendor Lookup", "deterministic"),
            Phase("Risk Refresh", "deterministic"),
            Phase("Invoice Match", "deterministic"),
            Phase("payment_release", "hitl"),
        ),
        hitl_gates=(
            HitlGate("payment_release", "payment_release_decision",
                     "vendor_kyc_finance_bp", wait_probability=0.2),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_vendor_risk_to_pay_workflow",
        realistic_interval_seconds=86400,
    ),
    "lead-to-cash": Domain(
        workflow_type="lead-to-cash",
        display_name="Lead to Cash",
        workflow_id_prefix="L2C",
        orchestrator_name="LeadToCashOrchestrator",
        operator_surface="account-director",
        phases=(
            Phase("Lead Intake", "deterministic"),
            Phase("Quote Build", "deterministic"),
            Phase("Order to Invoice", "deterministic"),
            Phase("revenue_recognition", "hitl"),
        ),
        hitl_gates=(
            HitlGate("revenue_recognition", "revenue_recognition_decision",
                     "account_director", wait_probability=0.2),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_lead_to_cash_workflow",
        realistic_interval_seconds=259200,
    ),
    "fy-close": Domain(
        workflow_type="fy-close",
        display_name="Fiscal-Year Close",
        workflow_id_prefix="FYC",
        orchestrator_name="FyCloseOrchestrator",
        operator_surface="ceo",
        phases=(
            Phase("Ledger Snapshot", "deterministic"),
            Phase("Reconciliation", "deterministic"),
            Phase("Variance Pack", "deterministic"),
            Phase("ceo_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("ceo_signoff", "fy_close_decision", "controller",
                     wait_probability=0.3),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_fy_close_workflow",
        realistic_interval_seconds=2592000,
    ),
    "board-prep": Domain(
        workflow_type="board-prep",
        display_name="Board Pack Preparation",
        workflow_id_prefix="BRD",
        orchestrator_name="BoardPrepOrchestrator",
        operator_surface="ceo",
        phases=(
            Phase("Pack Outline", "deterministic"),
            Phase("KPI Snapshot", "deterministic"),
            Phase("Narrative Draft", "deterministic"),
            Phase("board_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("board_signoff", "board_pack_decision", "cfo",
                     wait_probability=0.25, override_probability=0.05),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_board_prep_workflow",
        realistic_interval_seconds=2592000,
    ),

    # ----- pitch-c2: cross-domain meta-workflows ------------------------
    # Each meta-workflow's orchestrator is a minimal pass-through; the
    # spawn function synchronously emits 2-4 ``workflow.sub_spawned``
    # bus events targeting other live domains. The
    # ``MetaWorkflowReflector`` mirrors those into Workflow self-relations
    # via SUB_WORKFLOW_OF. The projection itself emits a single Workflow
    # node (the parent stamp); rels are owned by the reflector.
    "media-pitch-to-win": Domain(
        workflow_type="media-pitch-to-win",
        display_name="Media Pitch to Win",
        workflow_id_prefix="MPW",
        orchestrator_name="MediaPitchToWinOrchestrator",
        operator_surface="creative-director",
        phases=(
            Phase("Brief Intake", "deterministic"),
            Phase("Sub-Workflow Spawn", "deterministic"),
            Phase("creative_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("creative_signoff", "media_pitch_decision",
                     "creative_director", wait_probability=0.2),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_media_pitch_to_win_workflow",
        realistic_interval_seconds=1209600,
    ),
    "account-onboarding": Domain(
        workflow_type="account-onboarding",
        display_name="Account Onboarding",
        workflow_id_prefix="AOB",
        orchestrator_name="AccountOnboardingOrchestrator",
        operator_surface="account-director",
        phases=(
            Phase("Account Intake", "deterministic"),
            Phase("Sub-Workflow Spawn", "deterministic"),
            Phase("account_director_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("account_director_signoff", "account_onboarding_decision",
                     "account_director", wait_probability=0.15),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_account_onboarding_workflow",
        realistic_interval_seconds=604800,
    ),
    "intercompany-recharge": Domain(
        workflow_type="intercompany-recharge",
        display_name="Intercompany Recharge",
        workflow_id_prefix="ICR",
        orchestrator_name="IntercompanyRechargeOrchestrator",
        operator_surface="finance-controller",
        phases=(
            Phase("Recharge Intake", "deterministic"),
            Phase("Sub-Workflow Spawn", "deterministic"),
            Phase("controller_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("controller_signoff", "intercompany_recharge_decision",
                     "controller", wait_probability=0.2),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_intercompany_recharge_workflow",
        realistic_interval_seconds=2592000,
    ),
    "talent-redeployment": Domain(
        workflow_type="talent-redeployment",
        display_name="Talent Redeployment",
        workflow_id_prefix="TLR",
        orchestrator_name="TalentRedeploymentOrchestrator",
        operator_surface="hr-bp",
        phases=(
            Phase("Redeployment Intake", "deterministic"),
            Phase("Sub-Workflow Spawn", "deterministic"),
            Phase("hr_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("hr_signoff", "talent_redeployment_decision",
                     "hr_bp", wait_probability=0.2),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_talent_redeployment_workflow",
        realistic_interval_seconds=1209600,
    ),
    "agency-network-roll-up": Domain(
        workflow_type="agency-network-roll-up",
        display_name="Agency Network Roll-Up",
        workflow_id_prefix="ANR",
        orchestrator_name="AgencyNetworkRollUpOrchestrator",
        operator_surface="ceo",
        phases=(
            Phase("Network Snapshot", "deterministic"),
            Phase("Sub-Workflow Spawn", "deterministic"),
            Phase("ceo_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("ceo_signoff", "agency_rollup_decision", "cfo",
                     wait_probability=0.25),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_agency_network_roll_up_workflow",
        realistic_interval_seconds=2592000,
    ),
    "m-and-a-integration": Domain(
        workflow_type="m-and-a-integration",
        display_name="M&A Integration",
        workflow_id_prefix="MAI",
        orchestrator_name="MAndAIntegrationOrchestrator",
        operator_surface="ceo",
        phases=(
            Phase("Deal Intake", "deterministic"),
            Phase("Sub-Workflow Spawn", "deterministic"),
            Phase("ceo_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("ceo_signoff", "m_and_a_decision", "cfo",
                     wait_probability=0.4),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_m_and_a_integration_workflow",
        # M&A is rare — spawn at most every 1800s (30 min) of demo-warped
        # time so it doesn't dominate the activity stream.
        realistic_interval_seconds=1800,
        slow_burn=True,
    ),
    "crisis-response": Domain(
        workflow_type="crisis-response",
        display_name="Crisis Response",
        workflow_id_prefix="CRS",
        orchestrator_name="CrisisResponseOrchestrator",
        operator_surface="change-manager",
        phases=(
            Phase("Incident Intake", "deterministic"),
            Phase("Sub-Workflow Spawn", "deterministic"),
            Phase("ops_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("ops_signoff", "crisis_response_decision",
                     "change_manager", wait_probability=0.3),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_crisis_response_workflow",
        # Crisis is even rarer — spawn at most every 600s of demo time.
        realistic_interval_seconds=600,
    ),

    # ----- pitch-c3: agency-specific domains ---------------------------
    # Ten domains scoped to agency operations. Each has 3-4 deterministic
    # phases + 1 HITL gate using existing personae. Where an entity from
    # the pitch-e1 agency-domain kinds (Brand/Campaign/Pitch/MediaPlan)
    # naturally fits, the projection emits it.
    "creative-awards-submission": Domain(
        workflow_type="creative-awards-submission",
        display_name="Creative Awards Submission",
        workflow_id_prefix="CAS",
        orchestrator_name="CreativeAwardsSubmissionOrchestrator",
        operator_surface="creative-director",
        phases=(
            Phase("Submission Intake", "deterministic"),
            Phase("Award Brief Build", "deterministic"),
            Phase("creative_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("creative_signoff", "creative_awards_decision",
                     "creative_director", wait_probability=0.2),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_creative_awards_submission_workflow",
        realistic_interval_seconds=2592000,
    ),
    "client-renewal": Domain(
        workflow_type="client-renewal",
        display_name="Client Renewal",
        workflow_id_prefix="CLR",
        orchestrator_name="ClientRenewalOrchestrator",
        operator_surface="account-director",
        phases=(
            Phase("Renewal Intake", "deterministic"),
            Phase("Pitch Refresh", "deterministic"),
            Phase("Pricing Build", "deterministic"),
            Phase("account_director_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("account_director_signoff", "client_renewal_decision",
                     "account_director", wait_probability=0.2),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_client_renewal_workflow",
        realistic_interval_seconds=604800,
        slow_burn=True,
    ),
    "freelancer-onboarding": Domain(
        workflow_type="freelancer-onboarding",
        display_name="Freelancer Onboarding",
        workflow_id_prefix="FOB",
        orchestrator_name="FreelancerOnboardingOrchestrator",
        operator_surface="hr-bp",
        phases=(
            Phase("Freelancer Intake", "deterministic"),
            Phase("Compliance Check", "deterministic"),
            Phase("hr_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("hr_signoff", "freelancer_onboarding_decision",
                     "hr_bp", wait_probability=0.15),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_freelancer_onboarding_workflow",
        realistic_interval_seconds=86400,
    ),
    "data-clean-room-setup": Domain(
        workflow_type="data-clean-room-setup",
        display_name="Data Clean-Room Setup",
        workflow_id_prefix="DCR",
        orchestrator_name="DataCleanRoomSetupOrchestrator",
        operator_surface="data-bp",
        phases=(
            Phase("Clean-Room Intake", "deterministic"),
            Phase("Schema Negotiation", "deterministic"),
            Phase("Access Provisioning", "deterministic"),
            Phase("data_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("data_signoff", "data_clean_room_decision",
                     "chief_data_officer", wait_probability=0.25),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_data_clean_room_setup_workflow",
        realistic_interval_seconds=259200,
    ),
    "weekly-pitch-review": Domain(
        workflow_type="weekly-pitch-review",
        display_name="Weekly Pitch Review",
        workflow_id_prefix="WPR",
        orchestrator_name="WeeklyPitchReviewOrchestrator",
        operator_surface="creative-director",
        phases=(
            Phase("Pitch Roll-Up", "deterministic"),
            Phase("Critique Build", "deterministic"),
            Phase("creative_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("creative_signoff", "weekly_pitch_review_decision",
                     "creative_director", wait_probability=0.15),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_weekly_pitch_review_workflow",
        realistic_interval_seconds=604800,
    ),
    "monthly-client-pnl": Domain(
        workflow_type="monthly-client-pnl",
        display_name="Monthly Client P&L",
        workflow_id_prefix="MCP",
        orchestrator_name="MonthlyClientPnlOrchestrator",
        operator_surface="finance-controller",
        phases=(
            Phase("P&L Snapshot", "deterministic"),
            Phase("Variance Analysis", "deterministic"),
            Phase("controller_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("controller_signoff", "monthly_client_pnl_decision",
                     "controller", wait_probability=0.2),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_monthly_client_pnl_workflow",
        realistic_interval_seconds=2592000,
    ),
    "quarterly-creative-awards": Domain(
        workflow_type="quarterly-creative-awards",
        display_name="Quarterly Creative Awards",
        workflow_id_prefix="QCA",
        orchestrator_name="QuarterlyCreativeAwardsOrchestrator",
        operator_surface="creative-director",
        phases=(
            Phase("Award Slate", "deterministic"),
            Phase("Jury Critique", "deterministic"),
            Phase("creative_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("creative_signoff", "quarterly_creative_awards_decision",
                     "creative_director", wait_probability=0.2),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_quarterly_creative_awards_workflow",
        realistic_interval_seconds=7776000,
    ),
    "annual-budget-setting": Domain(
        workflow_type="annual-budget-setting",
        display_name="Annual Budget Setting",
        workflow_id_prefix="ABS",
        orchestrator_name="AnnualBudgetSettingOrchestrator",
        operator_surface="finance-controller",
        phases=(
            Phase("Budget Outline", "deterministic"),
            Phase("Function Roll-Up", "deterministic"),
            Phase("Variance Reconcile", "deterministic"),
            Phase("cfo_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("cfo_signoff", "annual_budget_decision", "cfo",
                     wait_probability=0.3),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_annual_budget_setting_workflow",
        realistic_interval_seconds=31536000,
        slow_burn=True,
    ),
    "new-business-pipeline-scrub": Domain(
        workflow_type="new-business-pipeline-scrub",
        display_name="New-Business Pipeline Scrub",
        workflow_id_prefix="NBP",
        orchestrator_name="NewBusinessPipelineScrubOrchestrator",
        operator_surface="account-director",
        phases=(
            Phase("Pipeline Snapshot", "deterministic"),
            Phase("Stage Hygiene", "deterministic"),
            Phase("account_director_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("account_director_signoff", "new_business_pipeline_decision",
                     "account_director", wait_probability=0.15),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_new_business_pipeline_scrub_workflow",
        realistic_interval_seconds=604800,
    ),
    "intercompany-talent-transfer": Domain(
        workflow_type="intercompany-talent-transfer",
        display_name="Intercompany Talent Transfer",
        workflow_id_prefix="ITT",
        orchestrator_name="IntercompanyTalentTransferOrchestrator",
        operator_surface="hr-bp",
        phases=(
            Phase("Transfer Intake", "deterministic"),
            Phase("Compliance Review", "deterministic"),
            Phase("hr_director_signoff", "hitl"),
        ),
        hitl_gates=(
            HitlGate("hr_director_signoff", "intercompany_talent_transfer_decision",
                     "hr_director", wait_probability=0.25),
        ),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_intercompany_talent_transfer_workflow",
        realistic_interval_seconds=1209600,
    ),
    # ----- autonomous-domain-insights v1 (Phase 5.1) -----
    # Generic one-shot workflow spawned by persona action approvals.
    # Not driven by the simulator (no spawn_fn); the route in Task 6.3
    # spawns it directly. Marked stub=True so live_domains() filters it
    # out of simulator/spawn contexts. The projection (Task 5.2) records
    # one Decision with phase="policy_set" carrying the proposed verdict.
    "policy_set": Domain(
        workflow_type="policy_set",
        display_name="Policy Set",
        workflow_id_prefix="POLICY",
        orchestrator_name="PolicySetOrchestrator",
        operator_surface="executive",
        phases=(
            Phase("record", "deterministic"),
        ),
        hitl_gates=(),
        skills=(),
        stub=True,
    ),
}


# --------------------------------------------------------------------------
# Lookup helpers — keep call sites readable.
# --------------------------------------------------------------------------


def get(workflow_type: str) -> Domain | None:
    """Return the registered Domain for a workflow_type, or None."""
    return DOMAINS.get(workflow_type)


def by_prefix(workflow_id: str) -> Domain | None:
    """Resolve a workflow_id (e.g. 'VKY-0007') to its Domain via prefix.

    Used by api/server/routes/workflows.py to synthesise minimal records
    when a fleet workflow isn't in the store. (Phase 2 of the plan
    upserts every workflow into the store, so this falls back to a no-op
    in steady state.)
    """
    prefix = workflow_id.split("-", 1)[0] if "-" in workflow_id else workflow_id
    for d in DOMAINS.values():
        if d.workflow_id_prefix == prefix:
            return d
    return None


def resolve_external_event(workflow_type: str, current_phase: str) -> str | None:
    """Map (workflow_type, current_phase) to the Durable external event name.

    Cold-cache fallback for the resolve route when the in-memory
    pending-gate cache has been cleared (e.g. FastAPI restart between
    suspend and operator click). Matches HitlGate.gate_phase exactly,
    case-insensitive, with underscore/space normalisation so
    "Manager Approval" and "manager_approval" both resolve.
    """
    domain = DOMAINS.get(workflow_type)
    if not domain:
        return None
    norm = current_phase.lower().replace(" ", "_")
    for gate in domain.hitl_gates:
        if gate.gate_phase.lower().replace(" ", "_") == norm:
            return gate.external_event
    return None


def all_wake_hints() -> set[str]:
    """Union of every domain's wake-hint event names.

    Triage layer (api/server/services/triage.py) uses this to extend
    `WAKE_TYPES` so per-domain anticipatory events wake the FM without
    each domain needing to edit api/shared/events.py.
    """
    out: set[str] = set()
    for d in DOMAINS.values():
        for wh in d.wake_hints:
            out.add(wh.event)
    return out


def all_personae() -> set[str]:
    """Set of every persona role referenced by any HITL gate.

    Used by the registry validation test to assert every persona has a
    SKILL.md under api/server/personae/.
    """
    out: set[str] = set()
    for d in DOMAINS.values():
        for g in d.hitl_gates:
            out.add(g.persona)
    return out


def live_domains() -> list[Domain]:
    """Return the runtime-spawnable domains (excludes ``stub=True`` entries).

    Use this in any code path that iterates over what the substrate
    actually runs (simulator, FM skill text, blueprint inventory, etc.).
    Reading ``DOMAINS.values()`` directly is fine for documentation /
    org-clone surfaces that need to see the full registry including
    placeholders.
    """
    return [d for d in DOMAINS.values() if not d.stub]
