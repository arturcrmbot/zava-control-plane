"""api/shared/personas.py — Persona registry: single source of truth.

Sister to `api/shared/domains.py`. Every persona's structural metadata
(role, archetype, scope, default authority band, workflow_label,
external_event_default, uses_authority_mcp) lives in `PERSONAS` keyed
by role.

Why this exists
---------------
Before this registry, persona metadata lived only in the YAML
frontmatter of `api/server/personae/<role>/SKILL.md`. Consumers
(`persona_responder`, `blueprint_inventory`, `fleet_manager_service`)
either re-parsed those files or hardcoded literals. Adding a persona
or shifting an archetype meant tracking down every consumer.

The registry is now the authoritative source. The `decision_policy`
block stays in the SKILL.md (it's the persona's *behaviour*, not
its *structure*); everything else lives here.

Consumers:
- api.server.services.persona_responder       — validates against registry at attach()
- api.server.services.blueprint_inventory     — renders persona library on the microsite
- api.server.services.fleet_manager_service   — composes "personae under supervision" text
- api.server.routes.personas (Phase 7)        — operator-facing persona library page

Engagement-POC swap: real engagements replace the registry data with a
customer-supplied org chart slice; the consumers don't change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Archetype = Literal["approver", "subject", "reviewer", "delegate", "notifier"]
ScopeFunction = Literal[
    "finance",
    "hr",
    "it",
    "procurement",
    "legal",
    "legal_privacy",
    "commercial",
    "candidate",
]


@dataclass(frozen=True)
class Persona:
    """A persona structural record. Behaviour lives in SKILL.md decision_policy.

    `archetype` groups personae for UI rendering and FM skill text:
      - approver: signs off the gate (most common).
      - subject:  the person the workflow is *about* (claimant, candidate).
      - reviewer: examines and may flag without final sign-off.
      - delegate: stands in for an absent approver.
      - notifier: receives information, no decision authority.

    `scope_function` is the corporate function the persona belongs to.
    `scope_business_unit` and `scope_geography` default to "*" (all).

    `default_authority_band` is a free-text label of the value band the
    persona typically signs off (e.g. "<=£500", "£10k-£50k", "any"). It
    is documentation only; the binding authority resolution comes from
    the delegated_authority MCP at runtime.

    `uses_authority_mcp = True` declares that the persona's
    decision_policy consults `context.authority` (or calls
    `authority_check` from the sandbox) to resolve thresholds, instead
    of inlining numeric values. The persona responder uses this flag to
    surface migration status in tests and on the microsite.
    """

    role: str
    archetype: Archetype
    scope_function: ScopeFunction
    workflow_label: str
    external_event_default: str | None = None
    scope_business_unit: str = "*"
    scope_geography: str = "*"
    default_authority_band: str | None = None
    uses_authority_mcp: bool = False
    description: str = ""


# --------------------------------------------------------------------------
# The registry. Entries grouped by domain to make code review easy.
# --------------------------------------------------------------------------

PERSONAS: dict[str, Persona] = {
    # ----- POC1 expense-claim -----
    "claim_submitter": Persona(
        role="claim_submitter",
        archetype="subject",
        scope_function="finance",
        workflow_label="Finance Compliance",
        external_event_default="justification",
        description="Submits a justification for a Red-routed expense claim awaiting employee response.",
    ),
    "ssc_reviewer": Persona(
        role="ssc_reviewer",
        archetype="reviewer",
        scope_function="finance",
        workflow_label="Finance Compliance",
        external_event_default="reviewer_decision",
        default_authority_band="<=£1,000 (delegation by category)",
        uses_authority_mcp=True,
        description="Accepts or rejects the SSC arbitration recommendation on a Red expense claim.",
    ),
    # ----- POC2 hiring -----
    "finance_bp": Persona(
        role="finance_bp",
        archetype="approver",
        scope_function="finance",
        workflow_label="Hiring",
        external_event_default="budget_approval",
        default_authority_band="<=£10,000 delta vs band midpoint",
        uses_authority_mcp=True,
        description="Approves or escalates a hire request based on the budget envelope check.",
    ),
    "hr_bp": Persona(
        role="hr_bp",
        archetype="approver",
        scope_function="hr",
        workflow_label="Hiring",
        external_event_default="offer_approval",
        description="Approves or rejects a final offer for a hire based on offer-personalisation output.",
    ),
    "recruiter": Persona(
        role="recruiter",
        archetype="approver",
        scope_function="hr",
        workflow_label="Hiring",
        external_event_default="interview_invite",
        description="Decides whether to invite a shortlisted candidate to interview, or whether to extend an offer.",
    ),
    "candidate": Persona(
        role="candidate",
        archetype="subject",
        scope_function="candidate",
        workflow_label="Hiring",
        external_event_default="voice_complete",
        description="Stands in for a real candidate at the voice screen, interview-slot pick, and offer accept/decline gates.",
    ),
    # ----- Travel pre-approval -----
    "line_manager": Persona(
        role="line_manager",
        archetype="approver",
        scope_function="hr",
        workflow_label="Travel pre-approval",
        external_event_default="manager_approval_decision",
        description="Approves or rejects a travel pre-approval request based on policy fit and cost band.",
    ),
    # ----- Vendor KYC -----
    "vendor_kyc_finance_bp": Persona(
        role="vendor_kyc_finance_bp",
        archetype="approver",
        scope_function="finance",
        workflow_label="Vendor onboarding & KYC",
        external_event_default="finance_signoff_decision",
        description="Approves a new vendor when entity sanctions, UBO sanctions, and adverse-media all clear; otherwise rejects.",
    ),
    # ----- Employee onboarding -----
    "onboarding_it_admin": Persona(
        role="onboarding_it_admin",
        archetype="approver",
        scope_function="it",
        workflow_label="Employee onboarding",
        external_event_default="it_admin_approval_decision",
        description="Approves or rejects a day-1 RBAC bundle based on separation-of-duties conflicts and template-default bundle size.",
    ),
    # ----- IT access request -----
    "it_access_line_manager": Persona(
        role="it_access_line_manager",
        archetype="approver",
        scope_function="it",
        workflow_label="IT access request",
        external_event_default="line_manager_approval_decision",
        description="Approves or rejects an IT access request based on business justification and the access-risk-assessor's overall risk score.",
    ),
    "it_access_it_admin": Persona(
        role="it_access_it_admin",
        archetype="approver",
        scope_function="it",
        workflow_label="IT access request",
        external_event_default="it_admin_approval_decision",
        description="Approves or rejects an IT access request based on the line manager's prior decision and SoD conflicts.",
    ),
    # ----- Contract renewal -----
    "contract_finance_bp": Persona(
        role="contract_finance_bp",
        archetype="approver",
        scope_function="finance",
        workflow_label="Contract renewal",
        external_event_default="finance_signoff_decision",
        default_authority_band="cost_change <=10% auto-approve, >25% escalate",
        uses_authority_mcp=True,
        description="Approves a contract renewal at or below 10% cost change; escalates above 25% (large price jumps need a human).",
    ),
    "contract_line_manager": Persona(
        role="contract_line_manager",
        archetype="approver",
        scope_function="commercial",
        workflow_label="Contract renewal",
        external_event_default="contract_owner_signoff_decision",
        description="Approves or rejects a contract renewal as the contract owner; defers to finance when finance has signed off.",
    ),
    # ----- Performance review -----
    "perf_review_hr_bp": Persona(
        role="perf_review_hr_bp",
        archetype="approver",
        scope_function="hr",
        workflow_label="Performance review",
        external_event_default="hr_calibration_decision",
        description="Approves or rejects a proposed performance calibration based on grade-band distribution fit and peer review count.",
    ),
    "perf_review_line_manager": Persona(
        role="perf_review_line_manager",
        archetype="approver",
        scope_function="hr",
        workflow_label="Performance review",
        external_event_default="line_manager_delivery_decision",
        description="Approves or rejects the line-manager delivery of the proposed rating; auto-approves once HR has calibrated.",
    ),
    # ----- Phase 6 graduated personae (compose-persona v1) -----
    # Available cast for forthcoming domains. Each carries an executable
    # decision_policy that consults the delegated-authority matrix; none
    # are wired into a domain registry HITL gate yet (see plan
    # feature-authority-and-personae-1.md Phase 6).
    #
    # Finance (4)
    "controller": Persona(
        role="controller",
        archetype="approver",
        scope_function="finance",
        workflow_label="AP / Finance",
        external_event_default="controller_signoff_decision",
        default_authority_band="£25k-£250k AP invoices and material expense claims",
        uses_authority_mcp=True,
        description="Approves AP invoices and material expense claims within the controller band; escalates to CFO above £250k.",
    ),
    "fpa_analyst": Persona(
        role="fpa_analyst",
        archetype="reviewer",
        scope_function="finance",
        workflow_label="Financial planning & analysis",
        external_event_default="variance_review_decision",
        default_authority_band="±10% variance tolerance",
        description="Reviews variance reports and budget reforecasts; flags material variances for the controller without final sign-off authority.",
    ),
    "ap_clerk": Persona(
        role="ap_clerk",
        archetype="subject",
        scope_function="finance",
        workflow_label="AP / Finance",
        external_event_default="ap_invoice_processing_decision",
        default_authority_band="<£25k three-way-matched invoices",
        uses_authority_mcp=True,
        description="Processes AP invoices via three-way match; auto-approves clean matches, escalates mismatches and high-value invoices to controller.",
    ),
    "treasurer": Persona(
        role="treasurer",
        archetype="approver",
        scope_function="finance",
        workflow_label="Treasury",
        external_event_default="treasury_signoff_decision",
        default_authority_band="<£1M FX hedges and cash-pool transfers",
        uses_authority_mcp=True,
        description="Approves treasury operations within the treasurer band; escalates to CFO above £1M.",
    ),
    # Procurement (3)
    "category_manager": Persona(
        role="category_manager",
        archetype="approver",
        scope_function="procurement",
        workflow_label="Procurement",
        external_event_default="po_approval_decision",
        default_authority_band="£5k-£50k POs against approved suppliers",
        uses_authority_mcp=True,
        description="Approves purchase orders within the category-manager band; validates against approved-supplier list; escalates strategic spend.",
    ),
    "sourcing_lead": Persona(
        role="sourcing_lead",
        archetype="approver",
        scope_function="procurement",
        workflow_label="Procurement",
        external_event_default="sourcing_event_decision",
        default_authority_band="£50k-£500k POs and RFP events",
        uses_authority_mcp=True,
        description="Approves high-band POs and runs RFP / sourcing events; coordinates with category managers and the CPO on strategic spend.",
    ),
    "cpo": Persona(
        role="cpo",
        archetype="approver",
        scope_function="procurement",
        workflow_label="Procurement",
        external_event_default="cpo_signoff_decision",
        default_authority_band=">£500k strategic POs",
        uses_authority_mcp=True,
        description="Chief Procurement Officer; sign-off authority for strategic POs and category-strategy approvals.",
    ),
    # Legal (3)
    "contracts_counsel": Persona(
        role="contracts_counsel",
        archetype="reviewer",
        scope_function="legal",
        workflow_label="Legal — contracts",
        external_event_default="contract_review_decision",
        default_authority_band="standard NDAs and MSAs ≤£250k",
        uses_authority_mcp=True,
        description="Reviews contracts (NDAs, MSAs, SOWs, vendor terms) and signs off on standard templates; escalates material deviations to GC.",
    ),
    "dpo": Persona(
        role="dpo",
        archetype="approver",
        scope_function="legal_privacy",
        workflow_label="Legal — privacy",
        external_event_default="dpia_signoff_decision",
        default_authority_band="DPIAs (low-risk solo, high-risk joint with GC)",
        uses_authority_mcp=True,
        description="Data Protection Officer; signs off on DPIAs and high-risk data processing assessments per GDPR Art. 35.",
    ),
    "gc": Persona(
        role="gc",
        archetype="approver",
        scope_function="legal",
        workflow_label="Legal — executive",
        external_event_default="gc_signoff_decision",
        default_authority_band="material MSAs, sanctions hits, escalated DPIAs",
        uses_authority_mcp=True,
        description="General Counsel; mandatory sign-off on material contracts, sanctions hits, and escalated DPIAs.",
    ),
    # Commercial (2)
    "account_director": Persona(
        role="account_director",
        archetype="approver",
        scope_function="commercial",
        workflow_label="Commercial — account",
        external_event_default="account_director_decision",
        default_authority_band="pitch resourcing ≤£50k, all pitch travel",
        uses_authority_mcp=True,
        description="Owns the client P&L line; sign-off authority for pitch resourcing and client-facing pitch travel.",
    ),
    "project_manager": Persona(
        role="project_manager",
        archetype="delegate",
        scope_function="commercial",
        workflow_label="Commercial — delivery",
        external_event_default="project_manager_decision",
        default_authority_band="±10% plan variance",
        description="Plans and tracks delivery for an account; subject of resourcing and timesheet approvals; delegates upward when resourcing exceeds plan.",
    ),
    # Cross-cutting (2)
    "change_manager": Persona(
        role="change_manager",
        archetype="approver",
        scope_function="it",
        workflow_label="IT — change & incident",
        external_event_default="change_management_decision",
        default_authority_band="P3/P4 incidents and routine change records",
        uses_authority_mcp=True,
        description="Approves IT change requests and incident triage outcomes; mandatory record on privileged-access grants.",
    ),
    "comp_ben_analyst": Persona(
        role="comp_ben_analyst",
        archetype="reviewer",
        scope_function="hr",
        workflow_label="HR — compensation",
        external_event_default="comp_ben_decision",
        default_authority_band="executive offers and calibration outliers",
        uses_authority_mcp=True,
        description="Reviews compensation calibrations and sizes executive offers; advisory authority on outlier ratings, sign-off on executive packages.",
    ),
}


# --------------------------------------------------------------------------
# Lookup helpers — keep call sites readable.
# --------------------------------------------------------------------------


def get(role: str) -> Persona | None:
    """Return the registered Persona for a role, or None."""
    return PERSONAS.get(role)


def by_archetype(archetype: Archetype) -> list[Persona]:
    """Return every Persona whose archetype matches."""
    return [p for p in PERSONAS.values() if p.archetype == archetype]


def by_function(function: ScopeFunction) -> list[Persona]:
    """Return every Persona whose scope_function matches."""
    return [p for p in PERSONAS.values() if p.scope_function == function]


def all_archetypes() -> set[str]:
    """Set of every archetype represented in the registry."""
    return {p.archetype for p in PERSONAS.values()}


def all_functions() -> set[str]:
    """Set of every scope_function represented in the registry."""
    return {p.scope_function for p in PERSONAS.values()}


def authority_users() -> list[Persona]:
    """Personae whose decision_policy reads context.authority instead of inlining thresholds."""
    return [p for p in PERSONAS.values() if p.uses_authority_mcp]
