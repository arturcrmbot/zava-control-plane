"""verticals/agency/functions.py — Agency organisational function registry.

Canonical Agency ``Function`` declarations. Each ``Function`` carries the
per-department identity block the FunctionFleetManager templates against
(KPIs, owned domains, persona hierarchy, ambient watchers).

Agency owns ten business functions (nine departments plus ``legacy`` for the
POC1/POC2 carry-over domains). It does not own ``customer-success`` — that
function belongs exclusively to the Telco pack (``verticals/telco/functions.py``).
The ``ops`` function here owns only ``crisis-response``; ``network-incident``
and ``order-to-activate`` are owned by Telco's ``network-operations``
function.

Function → domain wiring (the ``Domain.function`` back-reference) happens
once, at ``verticals.agency.manifest.build_pack()`` time, via
``verticals._helpers.wire_domain_functions``. Drift between this file's
``owns_domains`` enumeration and ``verticals/agency/domains.py`` trips that
wiring step's ownership-mismatch check.
"""
from __future__ import annotations

from api.shared.function_contracts import Function, PersonaTree


AGENCY_FUNCTIONS: dict[str, Function] = {
    "finance": Function(
        name="finance",
        display="Finance",
        operator_surface="finance-controller",
        owns_domains=("ap-invoice", "contract-renewal", "purchase-order",
                      "treasury-fx", "vendor-kyc", "vendor-risk-to-pay",
                      "intercompany-recharge",
                      "monthly-client-pnl", "annual-budget-setting"),
        # Phase 6 (TASK-035 / TASK-036) plants these instances; the names
        # are listed here so the discovery cross-validation has a target.
        # Phase 4 IP1 (TASK-006b) adds ``period-close`` (cadence-fired).
        ambient_agents=("budget-variance-watcher", "vendor-risk-watcher",
                        "period-close"),
        kpis=("dso", "dpo", "budget-variance-pct", "fraud-rate"),
        # D1 (pitch-d1): deepen the regional + BP-pod tier under controller.
        persona_hierarchy=PersonaTree(
            role="cfo",
            manages=(
                PersonaTree(role="controller", manages=(
                    PersonaTree(role="regional_controller_emea", manages=(
                        PersonaTree(role="bp_pod_lead", manages=(
                            PersonaTree(role="finance_bp"),
                            PersonaTree(role="ap_clerk"),
                            PersonaTree(role="fpa_analyst"),
                        )),
                    )),
                    PersonaTree(role="regional_controller_us", manages=(
                        PersonaTree(role="bp_pod_lead", manages=(
                            PersonaTree(role="finance_bp"),
                            PersonaTree(role="ap_clerk"),
                            PersonaTree(role="fpa_analyst"),
                        )),
                    )),
                )),
                PersonaTree(role="treasurer"),
            ),
        ),
    ),
    "hr": Function(
        name="hr",
        display="People & HR",
        operator_surface="hr-bp",
        owns_domains=("employee-onboarding", "perf-review", "travel-preapproval", "training-request",
                      "hire-to-productive", "talent-redeployment",
                      "freelancer-onboarding", "intercompany-talent-transfer",
                      "employee-transfer"),
        # Phase 4 IP1 (TASK-006b) adds ``morning-sweep`` (cadence-fired).
        # compose-domain v4 (fleet-employee-transfer) adds ``employee-transfer-watcher``.
        ambient_agents=("morning-sweep", "employee-transfer-watcher"),
        kpis=("time-to-hire", "regrettable-attrition-pct",
              "engagement-score", "comp-ratio"),
        # D1 (pitch-d1): hr_director → regional_hr_lead → hr_bp tier.
        persona_hierarchy=PersonaTree(
            role="cpo",
            manages=(
                PersonaTree(role="hr_director", manages=(
                    PersonaTree(role="regional_hr_lead", manages=(
                        PersonaTree(role="hr_bp", manages=(
                            PersonaTree(role="talent_coordinator"),
                        )),
                        PersonaTree(role="recruiter"),
                        PersonaTree(role="comp_ben_analyst"),
                    )),
                )),
                PersonaTree(role="perf_review_hr_bp"),
            ),
        ),
    ),
    "revenue": Function(
        name="revenue",
        display="Revenue",
        operator_surface="account-director",
        # Phase 4 IP5 graduates the synthetic ``lead-to-cash`` meta-workflow.
        owns_domains=("lead-to-cash", "account-onboarding",
                      "client-renewal", "new-business-pipeline-scrub"),
        ambient_agents=(),
        kpis=("pipeline-coverage", "win-rate", "arr-growth-pct", "nrr"),
        # D1 (pitch-d1): regional_account_lead → account_manager → coordinator.
        persona_hierarchy=PersonaTree(
            role="account_director",
            manages=(
                PersonaTree(role="regional_account_lead", manages=(
                    PersonaTree(role="account_manager", manages=(
                        PersonaTree(role="account_coordinator"),
                    )),
                )),
                PersonaTree(role="sourcing_lead"),
            ),
        ),
    ),
    "ops": Function(
        name="ops",
        display="Operations",
        operator_surface="change-manager",
        owns_domains=("crisis-response",),
        ambient_agents=(),
        kpis=("on-time-delivery-pct", "cycle-time", "incident-rate", "cost-per-unit"),
        # D1 (pitch-d1): change_manager → program_manager → project_manager → delivery_lead.
        persona_hierarchy=PersonaTree(
            role="change_manager",
            manages=(
                PersonaTree(role="program_manager", manages=(
                    PersonaTree(role="project_manager", manages=(
                        PersonaTree(role="delivery_lead"),
                    )),
                )),
            ),
        ),
    ),
    "legal": Function(
        name="legal",
        display="Legal",
        operator_surface="general-counsel",
        owns_domains=("contract-review", "privacy-dpia"),
        ambient_agents=(),
        kpis=("contract-cycle-time", "litigation-exposure",
              "policy-coverage-pct", "dpia-on-time-pct"),
        # D1 (pitch-d1): gc → contracts_counsel_senior → contracts_counsel.
        persona_hierarchy=PersonaTree(
            role="gc",
            manages=(
                PersonaTree(role="contracts_counsel_senior", manages=(
                    PersonaTree(role="contracts_counsel"),
                )),
                PersonaTree(role="dpo"),
            ),
        ),
    ),
    "marketing": Function(
        name="marketing",
        display="Marketing",
        operator_surface="creative-director",
        owns_domains=("creative-campaign", "media-pitch-to-win",
                      "creative-awards-submission", "weekly-pitch-review",
                      "quarterly-creative-awards"),
        ambient_agents=(),
        kpis=("campaign-roi", "brand-lift", "mql-volume", "creative-cycle-time"),
        # D1+D3 (pitch-d1, pitch-d3): creative tree + agency-services trees.
        # creative_director sits at the top; under it we plant the
        # creative chain (D1) plus the account-services, strategy/media,
        # production, talent/casting and data-science trees (D3).
        persona_hierarchy=PersonaTree(
            role="creative_director",
            manages=(
                # D1 — creative chain
                PersonaTree(role="ecd", manages=(
                    PersonaTree(role="cd", manages=(
                        PersonaTree(role="acd", manages=(
                            PersonaTree(role="senior_copywriter", manages=(
                                PersonaTree(role="mid_creative", manages=(
                                    PersonaTree(role="junior_creative"),
                                )),
                            )),
                            PersonaTree(role="senior_artworker", manages=(
                                PersonaTree(role="mid_creative", manages=(
                                    PersonaTree(role="junior_creative"),
                                )),
                            )),
                        )),
                    )),
                )),
                # D3 — account services
                PersonaTree(role="global_account_director", manages=(
                    PersonaTree(role="regional_account_director", manages=(
                        PersonaTree(role="account_director", manages=(
                            PersonaTree(role="account_manager", manages=(
                                PersonaTree(role="account_executive", manages=(
                                    PersonaTree(role="account_coordinator"),
                                )),
                            )),
                        )),
                    )),
                )),
                # D3 — strategy / planning / buying
                PersonaTree(role="head_of_strategy", manages=(
                    PersonaTree(role="strategy_director", manages=(
                        PersonaTree(role="planner"),
                        PersonaTree(role="media_planner", manages=(
                            PersonaTree(role="ad_ops_specialist"),
                        )),
                        PersonaTree(role="media_buyer", manages=(
                            PersonaTree(role="ad_ops_specialist"),
                        )),
                    )),
                )),
                # D3 — production
                PersonaTree(role="executive_producer", manages=(
                    PersonaTree(role="producer", manages=(
                        PersonaTree(role="production_coordinator"),
                    )),
                )),
                # D3 — talent / casting
                PersonaTree(role="casting_director", manages=(
                    PersonaTree(role="casting_assistant"),
                )),
                # D3 — data science
                PersonaTree(role="head_of_data_science", manages=(
                    PersonaTree(role="data_scientist"),
                )),
            ),
        ),
    ),
    "tech": Function(
        name="tech",
        display="Technology",
        operator_surface="it-admin",
        owns_domains=("it-access-request",),
        # Phase 6 (TASK-037) plants the AccessAnomalyWatcher instance.
        ambient_agents=("access-anomaly-watcher",),
        kpis=("change-failure-rate", "mttr", "access-review-coverage-pct",
              "deploy-frequency"),
        # D1 (pitch-d1): it_admin_director → it_access_it_admin → onboarding/line_manager → support_engineer.
        persona_hierarchy=PersonaTree(
            role="it_admin_director",
            manages=(
                PersonaTree(role="it_access_it_admin", manages=(
                    PersonaTree(role="onboarding_it_admin", manages=(
                        PersonaTree(role="support_engineer"),
                    )),
                    PersonaTree(role="it_access_line_manager", manages=(
                        PersonaTree(role="support_engineer"),
                    )),
                )),
            ),
        ),
    ),
    "data": Function(
        name="data",
        display="Data",
        operator_surface="data-bp",
        owns_domains=("data-clean-room-setup",),
        ambient_agents=(),
        kpis=("data-quality-score", "model-drift-rate",
              "platform-uptime-pct", "data-incident-rate"),
        # D1 (pitch-d1): chief_data_officer → data_lead → engineers → analyst.
        persona_hierarchy=PersonaTree(
            role="chief_data_officer",
            manages=(
                PersonaTree(role="data_lead", manages=(
                    PersonaTree(role="data_engineer", manages=(
                        PersonaTree(role="analyst"),
                    )),
                    PersonaTree(role="analytics_engineer", manages=(
                        PersonaTree(role="analyst"),
                    )),
                )),
            ),
        ),
    ),
    "ceo": Function(
        name="ceo",
        display="CEO Office",
        operator_surface="ceo",
        # CEO-FM owns two strategic domains (Phase 4 IP6 TASK-028).
        # Their orchestrators are codegen'd from briefs at
        # docs/superpowers/specs/{fy-close,board-prep}-brief.yaml; the
        # DOMAINS entries are stubs (phases=()) so the orphan validator
        # passes — full graduation lands in a later phase.
        owns_domains=("fy-close", "board-prep",
                      "agency-network-roll-up", "m-and-a-integration",
                      "policy_set"),
        # Phase 4 IP1 (TASK-006b) plants ``quarterly-okr``.
        ambient_agents=("quarterly-okr",),
        kpis=("revenue-growth", "ebitda-margin", "cash-runway"),
        # CEO has no dedicated SKILL.md persona today; reuse ``cfo`` as
        # the closest existing role until a CEO persona graduates.
        persona_hierarchy=PersonaTree(role="cfo"),
    ),
    "legacy": Function(
        name="legacy",
        display="Legacy (POC1/POC2 carry-over)",
        operator_surface="ssc-reviewer",
        owns_domains=("expense-claim", "hiring"),
        ambient_agents=(),
        kpis=(),  # legacy carries no KPIs
        # Sentinel — _validate_persona_hierarchy skips this role.
        persona_hierarchy=PersonaTree(role="__legacy__"),
    ),
}
