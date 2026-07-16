"""verticals/agency/authority.py — Agency vertical delegated-authority matrix.

Canonical Agency ``AuthorityRow`` declarations. Per-role authority data
(single-decision spend limit, approvable actions, OOO delegate, OOO flag)
for every Agency role, keyed by role.

This module owns Agency's authority rows exclusively — the four Telco-only
Customer Success roles (``cs_specialist``, ``cs_manager``,
``cs_account_director``, ``cs_director``) live in
``verticals/telco/authority.py`` and are never declared here.
``delivery_lead`` is a legitimately shared role used by both packs (same
row/behaviour in each pack today); it is declared here AND duplicated
verbatim in ``verticals/telco/authority.py`` rather than imported, so each
pack owns its full set of rows with no cross-pack import.

Consumers (via the ``api.shared.authority`` compatibility adapter):
- api.server.services.persona_responder — sandbox authority_check() calls
- decision_policy blocks in api/server/personae/*/SKILL.md
"""
from __future__ import annotations

from api.shared.authority_contracts import AuthorityRow


# --------------------------------------------------------------------------
# The matrix. Roles map 1:1 to ``api/server/personae/<role>/SKILL.md``.
# Defaults for personae not enumerated below: spend_limit_gbp=0.0, no
# approvable actions, delegate_to inferred from the persona hierarchy
# (the ``escalation cascade`` already resolves the parent at runtime).
# --------------------------------------------------------------------------

AGENCY_AUTHORITY: dict[str, AuthorityRow] = {
    # ----- Finance ------------------------------------------------------
    "ap_clerk": AuthorityRow(
        role="ap_clerk", spend_limit_gbp=1_000.0,
        approval_actions=("ap_invoice_approval",),
        delegate_to="controller",
    ),
    "finance_bp": AuthorityRow(
        role="finance_bp", spend_limit_gbp=10_000.0,
        approval_actions=("ap_invoice_approval", "expense_claim_approval", "budget_approval"),
        delegate_to="bp_pod_lead",
        ooo_today=True,  # demo: shows OOO routing on a finance BP
    ),
    "fpa_analyst": AuthorityRow(
        role="fpa_analyst", spend_limit_gbp=0.0,
        approval_actions=(),  # advisory only
        delegate_to="bp_pod_lead",
    ),
    "bp_pod_lead": AuthorityRow(
        role="bp_pod_lead", spend_limit_gbp=25_000.0,
        approval_actions=("ap_invoice_approval", "expense_claim_approval", "budget_approval"),
        delegate_to="regional_controller_emea",
    ),
    "regional_controller_emea": AuthorityRow(
        role="regional_controller_emea", spend_limit_gbp=100_000.0,
        approval_actions=("ap_invoice_approval", "expense_claim_approval",
                          "contract_approval", "budget_approval"),
        delegate_to="controller",
    ),
    "regional_controller_us": AuthorityRow(
        role="regional_controller_us", spend_limit_gbp=100_000.0,
        approval_actions=("ap_invoice_approval", "expense_claim_approval",
                          "contract_approval", "budget_approval"),
        delegate_to="controller",
    ),
    "controller": AuthorityRow(
        role="controller", spend_limit_gbp=250_000.0,
        approval_actions=("ap_invoice_approval", "expense_claim_approval",
                          "contract_approval", "budget_approval"),
        delegate_to="cfo",
    ),
    "finance_controller": AuthorityRow(
        role="finance_controller", spend_limit_gbp=500_000.0,
        approval_actions=("ap_invoice_approval", "expense_claim_approval",
                          "contract_approval", "budget_approval"),
        delegate_to="cfo",
    ),
    "treasurer": AuthorityRow(
        role="treasurer", spend_limit_gbp=1_000_000.0,
        approval_actions=("treasury_fx_hedge", "cash_pool_transfer"),
        delegate_to="cfo",
    ),
    "cfo": AuthorityRow(
        role="cfo", spend_limit_gbp=10_000_000.0,
        approval_actions=("ap_invoice_approval", "expense_claim_approval",
                          "contract_approval", "budget_approval",
                          "treasury_fx_hedge", "cash_pool_transfer",
                          "executive_offer_approval"),
        delegate_to=None,
    ),

    # ----- HR -----------------------------------------------------------
    "talent_coordinator": AuthorityRow(
        role="talent_coordinator", spend_limit_gbp=0.0,
        approval_actions=(), delegate_to="hr_bp",
    ),
    "recruiter": AuthorityRow(
        role="recruiter", spend_limit_gbp=2_500.0,
        approval_actions=("interview_invite", "candidate_offer"),
        delegate_to="hr_bp",
    ),
    "comp_ben_analyst": AuthorityRow(
        role="comp_ben_analyst", spend_limit_gbp=0.0,
        approval_actions=("comp_ben_decision",),
        delegate_to="hr_bp",
    ),
    "hr_bp": AuthorityRow(
        role="hr_bp", spend_limit_gbp=10_000.0,
        approval_actions=("offer_approval", "perf_review_calibration"),
        delegate_to="regional_hr_lead",
    ),
    "perf_review_hr_bp": AuthorityRow(
        role="perf_review_hr_bp", spend_limit_gbp=10_000.0,
        approval_actions=("perf_review_calibration",),
        delegate_to="hr_director",
    ),
    "regional_hr_lead": AuthorityRow(
        role="regional_hr_lead", spend_limit_gbp=50_000.0,
        approval_actions=("offer_approval", "perf_review_calibration", "hire_approval"),
        delegate_to="hr_director",
    ),
    "hr_director": AuthorityRow(
        role="hr_director", spend_limit_gbp=250_000.0,
        approval_actions=("offer_approval", "hire_approval", "executive_offer_approval"),
        delegate_to="cpo",
    ),
    "cpo": AuthorityRow(
        role="cpo", spend_limit_gbp=2_000_000.0,
        approval_actions=("hire_approval", "executive_offer_approval", "cpo_signoff_decision"),
        delegate_to=None,
    ),
    "line_manager": AuthorityRow(
        role="line_manager", spend_limit_gbp=2_500.0,
        approval_actions=("manager_approval_decision", "travel_preapproval"),
        delegate_to="hr_bp",
    ),

    # ----- Revenue / commercial ----------------------------------------
    "sourcing_lead": AuthorityRow(
        role="sourcing_lead", spend_limit_gbp=500_000.0,
        approval_actions=("sourcing_event_decision", "po_approval_decision"),
        delegate_to="cpo",
    ),
    "category_manager": AuthorityRow(
        role="category_manager", spend_limit_gbp=50_000.0,
        approval_actions=("po_approval_decision",),
        delegate_to="sourcing_lead",
    ),
    "account_coordinator": AuthorityRow(
        role="account_coordinator", spend_limit_gbp=1_000.0,
        approval_actions=(), delegate_to="account_manager",
    ),
    "account_manager": AuthorityRow(
        role="account_manager", spend_limit_gbp=10_000.0,
        approval_actions=("account_manager_decision",),
        delegate_to="regional_account_lead",
    ),
    "regional_account_lead": AuthorityRow(
        role="regional_account_lead", spend_limit_gbp=50_000.0,
        approval_actions=("regional_account_lead_decision",),
        delegate_to="account_director",
    ),
    "account_director": AuthorityRow(
        role="account_director", spend_limit_gbp=250_000.0,
        approval_actions=("account_director_decision", "pitch_resourcing"),
        delegate_to=None,
    ),

    # ----- Ops ----------------------------------------------------------
    "delivery_lead": AuthorityRow(
        role="delivery_lead", spend_limit_gbp=10_000.0,
        approval_actions=("delivery_lead_decision",),
        delegate_to="project_manager",
    ),
    "project_manager": AuthorityRow(
        role="project_manager", spend_limit_gbp=25_000.0,
        approval_actions=("project_manager_decision",),
        delegate_to="program_manager",
        ooo_today=True,  # demo: shows OOO routing on a project_manager
    ),
    "program_manager": AuthorityRow(
        role="program_manager", spend_limit_gbp=100_000.0,
        approval_actions=("program_manager_decision",),
        delegate_to="change_manager",
    ),
    "change_manager": AuthorityRow(
        role="change_manager", spend_limit_gbp=250_000.0,
        approval_actions=("change_management_decision", "incident_triage"),
        delegate_to=None,
    ),

    # ----- Legal --------------------------------------------------------
    "contracts_counsel": AuthorityRow(
        role="contracts_counsel", spend_limit_gbp=250_000.0,
        approval_actions=("contract_review_decision", "contract_approval"),
        delegate_to="contracts_counsel_senior",
    ),
    "contracts_counsel_senior": AuthorityRow(
        role="contracts_counsel_senior", spend_limit_gbp=2_500_000.0,
        approval_actions=("contract_review_decision", "contract_approval"),
        delegate_to="gc",
    ),
    "dpo": AuthorityRow(
        role="dpo", spend_limit_gbp=0.0,
        approval_actions=("dpia_signoff_decision",),
        delegate_to="gc",
    ),
    "gc": AuthorityRow(
        role="gc", spend_limit_gbp=25_000_000.0,
        approval_actions=("contract_review_decision", "contract_approval",
                          "dpia_signoff_decision", "gc_signoff_decision"),
        delegate_to=None,
    ),

    # ----- Marketing / creative ----------------------------------------
    "junior_creative": AuthorityRow(
        role="junior_creative", spend_limit_gbp=0.0,
        approval_actions=(), delegate_to="mid_creative",
    ),
    "mid_creative": AuthorityRow(
        role="mid_creative", spend_limit_gbp=1_000.0,
        approval_actions=("creative_review",),
        delegate_to="senior_copywriter",
    ),
    "senior_copywriter": AuthorityRow(
        role="senior_copywriter", spend_limit_gbp=2_500.0,
        approval_actions=("creative_review", "copy_signoff"),
        delegate_to="acd",
    ),
    "senior_artworker": AuthorityRow(
        role="senior_artworker", spend_limit_gbp=2_500.0,
        approval_actions=("creative_review", "art_signoff"),
        delegate_to="acd",
    ),
    "acd": AuthorityRow(
        role="acd", spend_limit_gbp=10_000.0,
        approval_actions=("acd_decision", "creative_signoff"),
        delegate_to="cd",
    ),
    "cd": AuthorityRow(
        role="cd", spend_limit_gbp=50_000.0,
        approval_actions=("cd_decision", "creative_signoff"),
        delegate_to="ecd",
        ooo_today=True,  # demo: shows OOO routing on a creative director
    ),
    "ecd": AuthorityRow(
        role="ecd", spend_limit_gbp=250_000.0,
        approval_actions=("ecd_decision", "creative_signoff"),
        delegate_to="creative_director",
    ),
    "creative_director": AuthorityRow(
        role="creative_director", spend_limit_gbp=1_000_000.0,
        approval_actions=("brief_approval_decision", "concept_lock",
                          "storyboard_approval", "final_signoff",
                          "creative_signoff"),
        delegate_to=None,
    ),

    # ----- Tech ---------------------------------------------------------
    "support_engineer": AuthorityRow(
        role="support_engineer", spend_limit_gbp=0.0,
        approval_actions=(), delegate_to="onboarding_it_admin",
    ),
    "onboarding_it_admin": AuthorityRow(
        role="onboarding_it_admin", spend_limit_gbp=2_500.0,
        approval_actions=("it_admin_approval_decision",),
        delegate_to="it_access_it_admin",
    ),
    "it_access_line_manager": AuthorityRow(
        role="it_access_line_manager", spend_limit_gbp=2_500.0,
        approval_actions=("line_manager_approval_decision",),
        delegate_to="it_access_it_admin",
    ),
    "it_access_it_admin": AuthorityRow(
        role="it_access_it_admin", spend_limit_gbp=10_000.0,
        approval_actions=("it_admin_approval_decision",),
        delegate_to="it_admin_director",
    ),
    "it_admin_director": AuthorityRow(
        role="it_admin_director", spend_limit_gbp=250_000.0,
        approval_actions=("it_admin_approval_decision", "change_management_decision"),
        delegate_to=None,
    ),

    # ----- Data ---------------------------------------------------------
    "analyst": AuthorityRow(
        role="analyst", spend_limit_gbp=0.0,
        approval_actions=(), delegate_to="data_engineer",
    ),
    "data_engineer": AuthorityRow(
        role="data_engineer", spend_limit_gbp=10_000.0,
        approval_actions=("data_engineer_decision",),
        delegate_to="data_lead",
    ),
    "analytics_engineer": AuthorityRow(
        role="analytics_engineer", spend_limit_gbp=10_000.0,
        approval_actions=("analytics_engineer_decision",),
        delegate_to="data_lead",
    ),
    "data_lead": AuthorityRow(
        role="data_lead", spend_limit_gbp=100_000.0,
        approval_actions=("data_lead_decision",),
        delegate_to="chief_data_officer",
    ),
    "chief_data_officer": AuthorityRow(
        role="chief_data_officer", spend_limit_gbp=2_500_000.0,
        approval_actions=("chief_data_officer_decision", "data_governance_signoff"),
        delegate_to=None,
    ),

    # ----- Vendor / contract / POC1+POC2 -------------------------------
    "vendor_kyc_finance_bp": AuthorityRow(
        role="vendor_kyc_finance_bp", spend_limit_gbp=10_000.0,
        approval_actions=("finance_signoff_decision",),
        delegate_to="contract_finance_bp",
    ),
    "contract_finance_bp": AuthorityRow(
        role="contract_finance_bp", spend_limit_gbp=25_000.0,
        approval_actions=("finance_signoff_decision",),
        delegate_to="controller",
    ),
    "contract_line_manager": AuthorityRow(
        role="contract_line_manager", spend_limit_gbp=25_000.0,
        approval_actions=("contract_owner_signoff_decision",),
        delegate_to="account_director",
    ),
    "ssc_reviewer": AuthorityRow(
        role="ssc_reviewer", spend_limit_gbp=1_000.0,
        approval_actions=("reviewer_decision", "expense_claim_approval"),
        delegate_to="controller",
    ),
    "claim_submitter": AuthorityRow(
        role="claim_submitter", spend_limit_gbp=0.0,
        approval_actions=(), delegate_to="ssc_reviewer",
    ),
    "candidate": AuthorityRow(
        role="candidate", spend_limit_gbp=0.0,
        approval_actions=(), delegate_to="recruiter",
    ),

    # ----- D3 (pitch-d3): agency-specific role library --------------
    # Account-services tree
    "global_account_director": AuthorityRow(
        role="global_account_director", spend_limit_gbp=2_500_000.0,
        approval_actions=("global_account_director_decision", "pitch_resourcing"),
        delegate_to="creative_director",
    ),
    "regional_account_director": AuthorityRow(
        role="regional_account_director", spend_limit_gbp=500_000.0,
        approval_actions=("regional_account_director_decision",),
        delegate_to="global_account_director",
    ),
    "account_executive": AuthorityRow(
        role="account_executive", spend_limit_gbp=2_500.0,
        approval_actions=("account_executive_decision",),
        delegate_to="account_manager",
    ),

    # Strategy / planning / buying
    "head_of_strategy": AuthorityRow(
        role="head_of_strategy", spend_limit_gbp=500_000.0,
        approval_actions=("head_of_strategy_decision",),
        delegate_to="creative_director",
    ),
    "strategy_director": AuthorityRow(
        role="strategy_director", spend_limit_gbp=100_000.0,
        approval_actions=("strategy_director_decision",),
        delegate_to="head_of_strategy",
    ),
    "planner": AuthorityRow(
        role="planner", spend_limit_gbp=10_000.0,
        approval_actions=("planner_decision",),
        delegate_to="strategy_director",
    ),
    "media_planner": AuthorityRow(
        role="media_planner", spend_limit_gbp=50_000.0,
        approval_actions=("media_planner_decision", "media_plan_signoff"),
        delegate_to="strategy_director",
    ),
    "media_buyer": AuthorityRow(
        role="media_buyer", spend_limit_gbp=250_000.0,
        approval_actions=("media_buyer_decision", "media_buy_signoff"),
        delegate_to="strategy_director",
    ),
    "ad_ops_specialist": AuthorityRow(
        role="ad_ops_specialist", spend_limit_gbp=0.0,
        approval_actions=(), delegate_to="media_planner",
    ),

    # Production
    "executive_producer": AuthorityRow(
        role="executive_producer", spend_limit_gbp=500_000.0,
        approval_actions=("executive_producer_decision", "production_budget_signoff"),
        delegate_to="creative_director",
    ),
    "producer": AuthorityRow(
        role="producer", spend_limit_gbp=100_000.0,
        approval_actions=("producer_decision",),
        delegate_to="executive_producer",
    ),
    "production_coordinator": AuthorityRow(
        role="production_coordinator", spend_limit_gbp=2_500.0,
        approval_actions=(), delegate_to="producer",
    ),

    # Talent / casting
    "casting_director": AuthorityRow(
        role="casting_director", spend_limit_gbp=100_000.0,
        approval_actions=("casting_director_decision", "talent_signoff"),
        delegate_to="executive_producer",
    ),
    "casting_assistant": AuthorityRow(
        role="casting_assistant", spend_limit_gbp=0.0,
        approval_actions=(), delegate_to="casting_director",
    ),

    # Data science
    "head_of_data_science": AuthorityRow(
        role="head_of_data_science", spend_limit_gbp=250_000.0,
        approval_actions=("head_of_data_science_decision", "model_signoff"),
        delegate_to="creative_director",
    ),
    "data_scientist": AuthorityRow(
        role="data_scientist", spend_limit_gbp=10_000.0,
        approval_actions=("data_scientist_decision",),
        delegate_to="head_of_data_science",
    ),
}
