"""Legacy all-authority declarations used while vertical packs are extracted.

pitch-d2 (track D, plan/feature-enterprise-pitch-readiness-1.md).

Per-role authority data (single-decision spend limit, approvable
actions, OOO delegate, OOO flag) consolidated into ONE table. Replaces
the per-persona inline thresholds previously scattered across
``api/server/personae/*/SKILL.md``.

The ``authority_check`` callable mirrors the return shape of
``api.server.services.persona_responder._sandbox_authority_check`` —
``{"allowed": bool, "reason": str, "governing_rule_id": str | None}``
— so existing ``decision_policy`` blocks (which destructure the dict)
keep working unchanged.

H3 (cross-domain entanglement) is the work that actually consumes
``delegate_to`` + ``ooo_today`` to re-route an approval. D2 only
provides the data; the routing change lands separately.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthorityRow:
    """One row of the delegated-authority matrix."""

    role: str
    spend_limit_gbp: float
    approval_actions: tuple[str, ...]
    delegate_to: str | None
    ooo_today: bool = False


# --------------------------------------------------------------------------
# The matrix. Roles map 1:1 to ``api/server/personae/<role>/SKILL.md``.
# Defaults for personae not enumerated below: spend_limit_gbp=0.0, no
# approvable actions, delegate_to inferred from the persona hierarchy
# (the ``escalation cascade`` already resolves the parent at runtime).
# --------------------------------------------------------------------------

AUTHORITY: dict[str, AuthorityRow] = {
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
    # ----- Customer Success --------------------------------------------
    "cs_specialist": AuthorityRow(
        role="cs_specialist", spend_limit_gbp=0.0,
        approval_actions=(), delegate_to="cs_manager",
    ),
    "cs_manager": AuthorityRow(
        role="cs_manager", spend_limit_gbp=10_000.0,
        approval_actions=("cs_manager_decision",),
        delegate_to="cs_account_director",
    ),
    "cs_account_director": AuthorityRow(
        role="cs_account_director", spend_limit_gbp=100_000.0,
        approval_actions=("cs_account_director_decision",),
        delegate_to="cs_director",
    ),
    "cs_director": AuthorityRow(
        role="cs_director", spend_limit_gbp=500_000.0,
        approval_actions=("cs_director_decision",),
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


def authority_check(
    role: str,
    action: str,
    value: float | None = None,
    category: str | None = None,
    business_unit: str | None = None,
    geography: str | None = None,
    requester_role: str | None = None,
) -> dict:
    """Data-driven authority resolution against ``AUTHORITY``.

    Returns the SAME shape as
    ``api.server.services.persona_responder._sandbox_authority_check``:
    ``{"allowed": bool, "reason": str, "governing_rule_id": str|None}``.

    Resolution order:
      1. role unknown → deny.
      2. action not in role's ``approval_actions`` → deny.
      3. ``value`` exceeds ``spend_limit_gbp`` → deny (escalation hint
         in the reason).
      4. otherwise → allow.

    ``business_unit``, ``geography`` and ``requester_role`` are accepted
    for parity with the original sandbox helper. They aren't used by
    the matrix today but allow callers to pass them through unchanged.
    """
    row = AUTHORITY.get(role)
    if row is None:
        return {
            "allowed": False,
            "reason": f"role '{role}' not in authority matrix",
            "governing_rule_id": None,
        }
    if action not in row.approval_actions:
        return {
            "allowed": False,
            "reason": (
                f"role '{role}' is not authorised for action '{action}' "
                f"(authorised: {list(row.approval_actions)})"
            ),
            "governing_rule_id": f"AUTH-{role}-deny-action",
        }
    if value is not None and value > row.spend_limit_gbp:
        return {
            "allowed": False,
            "reason": (
                f"value GBP {value} exceeds {role} spend limit "
                f"GBP {row.spend_limit_gbp}"
            ),
            "governing_rule_id": f"AUTH-{role}-spend-limit",
        }
    return {
        "allowed": True,
        "reason": (
            f"{role} authorised for {action} "
            f"(value={value}, category={category})"
        ),
        "governing_rule_id": f"AUTH-{role}-{action}",
    }


def delegate_for(role: str) -> str | None:
    """Return the OOO delegate for ``role`` if recorded; else None."""
    row = AUTHORITY.get(role)
    return row.delegate_to if row else None


def is_ooo(role: str) -> bool:
    """True iff ``role`` is hand-flagged OOO for the demo."""
    row = AUTHORITY.get(role)
    return bool(row and row.ooo_today)
