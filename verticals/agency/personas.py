"""verticals/agency/personas.py — Agency vertical persona metadata registry.

Canonical Agency ``Persona`` declarations. Every persona's structural
metadata (role, archetype, scope, default authority band, workflow_label,
external_event_default, uses_authority_mcp, display_color) for the Agency
pack lives in ``AGENCY_PERSONAS`` keyed by role, aligned with the roles
enumerated by ``AGENCY_DOMAINS``' HITL gates and ``AGENCY_FUNCTIONS``'
persona hierarchies.

This module owns Agency's persona metadata exclusively — the four
Telco-only Customer Success roles (``cs_director``, ``cs_account_director``,
``cs_manager``, ``cs_specialist``) live in ``verticals/telco/personas.py``
and are never declared here. ``delivery_lead`` is a legitimately shared
role used by both packs (same metadata/behaviour in each pack today); it is
declared here AND duplicated verbatim in ``verticals/telco/personas.py``
rather than imported, so each pack owns its full set of personae with no
cross-pack import.

Consumers (via the ``api.shared.personas`` compatibility adapter):
- api.server.services.persona_responder       — validates against registry at attach()
- api.server.services.blueprint_inventory     — renders persona library on the microsite
- api.server.services.fleet_manager_service   — composes "personae under supervision" text
- api.server.routes.personas (Phase 7)        — operator-facing persona library page
"""
from __future__ import annotations

import dataclasses as _dataclasses

from api.shared.persona_contracts import Archetype, Persona, ScopeFunction


__all__ = ["Archetype", "ScopeFunction", "Persona", "AGENCY_PERSONAS"]


# --------------------------------------------------------------------------
# The registry. Entries grouped by domain to make code review easy.
# --------------------------------------------------------------------------

_AGENCY_PERSONAS: dict[str, Persona] = {
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

    # ----- Top-tier finance escalation targets (registered to make the
    #       dynamic-persona orchestrators in purchase-order, contract-review,
    #       privacy-dpia and treasury-fx work cleanly when matrix lookups
    #       resolve to these roles) -----
    "finance_controller": Persona(
        role="finance_controller",
        archetype="approver",
        scope_function="finance",
        workflow_label="Finance — controller",
        external_event_default="finance_controller_signoff_decision",
        default_authority_band="material expense / AP / contract renewal above BP delegation",
        uses_authority_mcp=True,
        description="Finance Controller; sign-off authority for material commitments above the BP delegation but below CFO.",
    ),
    "cfo": Persona(
        role="cfo",
        archetype="approver",
        scope_function="finance",
        workflow_label="Finance — executive",
        external_event_default="cfo_signoff_decision",
        default_authority_band="top-band finance — material AP, executive offers, large hedges, top-band travel",
        uses_authority_mcp=True,
        description="Chief Financial Officer; sign-off authority for top-band finance commitments across every domain.",
    ),

    # ----- POC3 creative-campaign -----
    # One persona owns all five HITL gates (brief_capture + ◆1..◆4); the
    # decision_policy block branches on `phase`. See
    # api/server/personae/creative_director/SKILL.md.
    "creative_director": Persona(
        role="creative_director",
        archetype="approver",
        scope_function="commercial",
        workflow_label="Creative Campaign",
        external_event_default="brief_approval_decision",
        description=(
            "Owns the five HITL gates of a creative campaign: brief capture (voice intake),"
            " brief approval, concept lock, storyboard approval, final signoff."
        ),
    ),

    # ----- D1 (pitch-d1): deepened function persona hierarchies -----
    # Finance regional + BP pod tier
    "regional_controller_emea": Persona(
        role="regional_controller_emea", archetype="approver", scope_function="finance",
        workflow_label="Finance — regional", external_event_default="regional_controller_emea_decision",
        default_authority_band="EMEA controller band", uses_authority_mcp=True,
        description="Regional Controller EMEA; sign-off authority within the EMEA controller band; escalates to group controller.",
    ),
    "regional_controller_us": Persona(
        role="regional_controller_us", archetype="approver", scope_function="finance",
        workflow_label="Finance — regional", external_event_default="regional_controller_us_decision",
        default_authority_band="US controller band", uses_authority_mcp=True,
        description="Regional Controller US; sign-off authority within the US controller band; escalates to group controller.",
    ),
    "bp_pod_lead": Persona(
        role="bp_pod_lead", archetype="approver", scope_function="finance",
        workflow_label="Finance — business partnering", external_event_default="bp_pod_lead_decision",
        default_authority_band="finance BP pod first-line band", uses_authority_mcp=True,
        description="Finance Business Partner pod lead; coordinates the finance BP pod; first-line approver under the regional controller.",
    ),

    # HR director / regional / coordinator tier
    "hr_director": Persona(
        role="hr_director", archetype="approver", scope_function="hr",
        workflow_label="People & HR — director", external_event_default="hr_director_decision",
        description="HR Director; sign-off authority for senior HR matters; escalates strategic decisions to the CPO.",
    ),
    "regional_hr_lead": Persona(
        role="regional_hr_lead", archetype="approver", scope_function="hr",
        workflow_label="People & HR — regional", external_event_default="regional_hr_lead_decision",
        description="Regional HR Lead; coordinates HR business partners across a region; escalates to HR Director.",
    ),
    "talent_coordinator": Persona(
        role="talent_coordinator", archetype="subject", scope_function="hr",
        workflow_label="People & HR — talent", external_event_default="talent_coordinator_decision",
        description="Talent Coordinator; supports recruiters and HR BPs with scheduling, candidate logistics, and onboarding handoffs.",
    ),

    # Revenue tier
    "regional_account_lead": Persona(
        role="regional_account_lead", archetype="approver", scope_function="commercial",
        workflow_label="Revenue — regional", external_event_default="regional_account_lead_decision",
        description="Regional Account Lead; coordinates account managers across a region; escalates strategic accounts to the account director.",
    ),
    "account_manager": Persona(
        role="account_manager", archetype="approver", scope_function="commercial",
        workflow_label="Revenue — account", external_event_default="account_manager_decision",
        description="Account Manager; owns day-to-day account relationships; sign-off authority within the account-manager band.",
    ),
    "account_coordinator": Persona(
        role="account_coordinator", archetype="subject", scope_function="commercial",
        workflow_label="Revenue — account", external_event_default="account_coordinator_decision",
        description="Account Coordinator; supports account managers with scheduling, status reporting, and routine client requests.",
    ),

    # Ops tier
    "program_manager": Persona(
        role="program_manager", archetype="approver", scope_function="commercial",
        workflow_label="Operations — programme", external_event_default="program_manager_decision",
        description="Programme Manager; coordinates a portfolio of related projects; escalates to the change manager.",
    ),
    "delivery_lead": Persona(
        role="delivery_lead", archetype="approver", scope_function="commercial",
        workflow_label="Operations — delivery", external_event_default="delivery_lead_decision",
        description="Delivery Lead; owns delivery within a single project workstream; first-line approver under the project manager.",
    ),

    # Legal tier
    "contracts_counsel_senior": Persona(
        role="contracts_counsel_senior", archetype="approver", scope_function="legal",
        workflow_label="Legal — contracts", external_event_default="contracts_counsel_senior_decision",
        default_authority_band="senior counsel band", uses_authority_mcp=True,
        description="Senior Contracts Counsel; sign-off on material contracts within the senior counsel band; escalates to GC.",
    ),

    # Marketing creative tier
    "ecd": Persona(
        role="ecd", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — creative", external_event_default="ecd_decision",
        description="Executive Creative Director; senior creative sign-off; escalates strategic creative decisions to the creative director.",
    ),
    "cd": Persona(
        role="cd", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — creative", external_event_default="cd_decision",
        description="Creative Director (account-level); sign-off on creative output for an account or campaign; escalates to ECD.",
    ),
    "acd": Persona(
        role="acd", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — creative", external_event_default="acd_decision",
        description="Associate Creative Director; runs a creative pod; first-line approver under the CD.",
    ),
    "senior_copywriter": Persona(
        role="senior_copywriter", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — creative", external_event_default="senior_copywriter_decision",
        description="Senior Copywriter; leads copy on an account; reviews mid/junior copy; escalates concept-level decisions to ACD.",
    ),
    "senior_artworker": Persona(
        role="senior_artworker", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — creative", external_event_default="senior_artworker_decision",
        description="Senior Artworker; leads art-direction execution on an account; reviews mid/junior artwork.",
    ),
    "mid_creative": Persona(
        role="mid_creative", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — creative", external_event_default="mid_creative_decision",
        description="Mid-level creative; produces copy or art under senior creative direction; escalates to senior creative.",
    ),
    "junior_creative": Persona(
        role="junior_creative", archetype="subject", scope_function="commercial",
        workflow_label="Marketing — creative", external_event_default="junior_creative_decision",
        description="Junior creative; produces first-pass copy or art under mid/senior creative direction.",
    ),

    # Tech tier
    "it_admin_director": Persona(
        role="it_admin_director", archetype="approver", scope_function="it",
        workflow_label="Technology — IT admin", external_event_default="it_admin_director_decision",
        description="IT Admin Director; senior tech sign-off; escalates strategic IT decisions to the CTO.",
    ),
    "support_engineer": Persona(
        role="support_engineer", archetype="subject", scope_function="it",
        workflow_label="Technology — support", external_event_default="support_engineer_decision",
        description="Support Engineer; first-line IT support; escalates incidents to IT admins or the change manager.",
    ),

    # Data tier
    "chief_data_officer": Persona(
        role="chief_data_officer", archetype="approver", scope_function="commercial",
        workflow_label="Data — executive", external_event_default="chief_data_officer_decision",
        description="Chief Data Officer; sign-off on strategic data initiatives, governance policy, and material data risks.",
    ),
    "data_lead": Persona(
        role="data_lead", archetype="approver", scope_function="commercial",
        workflow_label="Data — lead", external_event_default="data_lead_decision",
        description="Data Lead; coordinates data engineers and analytics engineers within a domain; escalates to CDO.",
    ),
    "data_engineer": Persona(
        role="data_engineer", archetype="approver", scope_function="commercial",
        workflow_label="Data — engineering", external_event_default="data_engineer_decision",
        description="Data Engineer; owns ingestion, modelling, and pipeline health; escalates platform-wide changes to data lead.",
    ),
    "analytics_engineer": Persona(
        role="analytics_engineer", archetype="approver", scope_function="commercial",
        workflow_label="Data — analytics", external_event_default="analytics_engineer_decision",
        description="Analytics Engineer; owns the analytics layer; escalates dimensional-model changes to data lead.",
    ),
    "analyst": Persona(
        role="analyst", archetype="reviewer", scope_function="commercial",
        workflow_label="Data — analyst", external_event_default="analyst_decision",
        description="Analyst; produces ad-hoc analysis and dashboards; flags anomalies for data engineering.",
    ),

    # ----- D3 (pitch-d3): agency-specific role library under marketing -----
    # Account-services tree
    "global_account_director": Persona(
        role="global_account_director", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — account services", external_event_default="global_account_director_decision",
        description="Global Account Director; owns the global P&L for a strategic account; escalates board-level decisions to the creative director.",
    ),
    "regional_account_director": Persona(
        role="regional_account_director", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — account services", external_event_default="regional_account_director_decision",
        description="Regional Account Director; owns the regional P&L for an account; escalates to Global Account Director.",
    ),
    "account_executive": Persona(
        role="account_executive", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — account services", external_event_default="account_executive_decision",
        description="Account Executive; runs day-to-day account work under the account manager.",
    ),

    # Strategy / planning / buying
    "head_of_strategy": Persona(
        role="head_of_strategy", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — strategy", external_event_default="head_of_strategy_decision",
        description="Head of Strategy; sign-off on strategic plans across accounts; escalates to creative director.",
    ),
    "strategy_director": Persona(
        role="strategy_director", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — strategy", external_event_default="strategy_director_decision",
        description="Strategy Director; runs the strategy team for an account or vertical; escalates to Head of Strategy.",
    ),
    "planner": Persona(
        role="planner", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — planning", external_event_default="planner_decision",
        description="Strategic Planner; develops account plans and brand strategy; escalates to Strategy Director.",
    ),
    "media_planner": Persona(
        role="media_planner", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — media", external_event_default="media_planner_decision",
        description="Media Planner; designs media plans and channel mix; escalates to Strategy Director.",
    ),
    "media_buyer": Persona(
        role="media_buyer", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — media", external_event_default="media_buyer_decision",
        description="Media Buyer; negotiates and books media placements; escalates spend overruns to Strategy Director.",
    ),
    "ad_ops_specialist": Persona(
        role="ad_ops_specialist", archetype="subject", scope_function="commercial",
        workflow_label="Marketing — ad ops", external_event_default="ad_ops_specialist_decision",
        description="Ad Operations Specialist; trafficks creative, monitors delivery, and reconciles billing.",
    ),

    # Production
    "executive_producer": Persona(
        role="executive_producer", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — production", external_event_default="executive_producer_decision",
        description="Executive Producer; sign-off on production budgets and vendor selection; escalates to creative director.",
    ),
    "producer": Persona(
        role="producer", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — production", external_event_default="producer_decision",
        description="Producer; owns delivery of a single production; escalates overruns to Executive Producer.",
    ),
    "production_coordinator": Persona(
        role="production_coordinator", archetype="subject", scope_function="commercial",
        workflow_label="Marketing — production", external_event_default="production_coordinator_decision",
        description="Production Coordinator; supports producer with scheduling, vendor logistics, and on-set coordination.",
    ),

    # Talent / casting
    "casting_director": Persona(
        role="casting_director", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — casting", external_event_default="casting_director_decision",
        description="Casting Director; sign-off on talent selection for productions; escalates union/usage exposure to executive producer.",
    ),
    "casting_assistant": Persona(
        role="casting_assistant", archetype="subject", scope_function="commercial",
        workflow_label="Marketing — casting", external_event_default="casting_assistant_decision",
        description="Casting Assistant; supports casting director with talent sourcing, scheduling, and release paperwork.",
    ),

    # Data science
    "head_of_data_science": Persona(
        role="head_of_data_science", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — data science", external_event_default="head_of_data_science_decision",
        description="Head of Data Science; sign-off on modelling approach and measurement frameworks for marketing.",
    ),
    "data_scientist": Persona(
        role="data_scientist", archetype="approver", scope_function="commercial",
        workflow_label="Marketing — data science", external_event_default="data_scientist_decision",
        description="Data Scientist; builds attribution and effectiveness models; escalates methodology to Head of Data Science.",
    ),

    # ----- Cross-domain executive synthesis (autonomous-domain-insights v1) -----
    "ceo": Persona(
        role="ceo",
        archetype="approver",
        scope_function="finance",
        workflow_label="Executive — synthesis",
        external_event_default="ceo_synthesis_decision",
        default_authority_band="any",
        description=("Chief Executive Officer. Synthesises domain-persona Insights "
                     "into a single org-wide narrative. Does not gate workflows in v1."),
    ),
}

AGENCY_DISPLAY_COLORS: dict[str, str] = {
    # Finance family — blue tones
    "cfo": "#4f9bff",
    "controller": "#6db3ff",
    "ap_clerk": "#88c4ff",
    "treasurer": "#2d7df5",
    "fpa_analyst": "#3a8aef",
    # HR / People — warm rose tones
    "cpo": "#ff7e9b",
    "hr_director": "#ff95ad",
    "hr_bp": "#f06b86",
    "recruiter": "#d65273",
    # Procurement / Vendor — amber / gold
    "sourcing_lead": "#f0a73a",
    "vendor_kyc_finance_bp": "#ffb84d",
    "contract_finance_bp": "#d68f29",
    # Tech / IT / Data — teal / cyan
    "it_admin_director": "#3dd6c8",
    "it_access_it_admin": "#5ce0d3",
    "data_lead": "#2bbeb1",
    "chief_data_officer": "#4adcd0",
    "head_of_data_science": "#58e3d6",
    # Creative — violet / magenta
    "ecd": "#b577ff",
    "cd": "#c98aff",
    "creative_director": "#9d5ee5",
    "executive_producer": "#af6ff5",
    "ad_ops_specialist": "#a26be0",
    "senior_artworker": "#bb84f0",
    "senior_copywriter": "#c890ff",
    # Legal / Privacy — emerald
    "gc": "#5cd6a8",
    "contracts_counsel": "#7ce0bb",
    "contracts_counsel_senior": "#44c393",
    "dpo": "#6ad8a5",
    # CEO + leadership — warm white / gold
    "ceo": "#fff3b8",
    # Account / CS — sky blue
    "account_director": "#7fc4ff",
    "account_manager": "#7fc4ff",
}

AGENCY_PERSONAS: dict[str, Persona] = {
    role: (
        _dataclasses.replace(p, display_color=AGENCY_DISPLAY_COLORS[role])
        if role in AGENCY_DISPLAY_COLORS
        else p
    )
    for role, p in _AGENCY_PERSONAS.items()
}
