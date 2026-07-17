from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


EngineCode = Literal["DDA", "FSP", "CTR", "OFV", "RIG", "ARA"]
MutationFamily = Literal["network", "operations", "commercial", "plan"]
PhaseKind = Literal["deterministic", "agent", "hitl"]

ENGINE_CODES = frozenset({"DDA", "FSP", "CTR", "OFV", "RIG", "ARA"})

SKILLS_BY_CODE = {
    "EC": "evidence-correlator",
    "RIA": "risk-impact-assessor",
    "NBA": "next-best-action-planner",
    "RM": "resource-matcher",
    "PE": "policy-entitlement-evaluator",
    "ER": "exception-resolution-advisor",
    "CD": "communication-drafter",
    "SC": "scenario-comparator",
}
SKILL_NAMES = frozenset(SKILLS_BY_CODE.values())

TOOLS_BY_PACK = {
    "network": (
        "network_query_state",
        "network_query_impact",
        "network_validate_action",
        "network_prepare_action",
    ),
    "operations": (
        "operations_query_case",
        "operations_search_runbook",
        "operations_match_resources",
        "operations_prepare_case_action",
    ),
    "commercial": (
        "commercial_query_customer",
        "commercial_query_order_revenue",
        "commercial_evaluate_entitlement",
        "commercial_prepare_action",
    ),
    "twin": (
        "twin_forecast",
        "twin_compare_scenarios",
        "twin_query_external_signal",
        "twin_publish_plan",
    ),
}

ENGINE_BOUNDARIES: dict[EngineCode, tuple[str, tuple[str, ...]]] = {
    "DDA": ("Detect Signal", ("Execute Action", "Verify Outcome")),
    "FSP": ("Build Forecast", ("Publish Plan", "Verify Outcome")),
    "CTR": ("Open Case", ("Resolve Case", "Confirm Resolution")),
    "OFV": ("Validate Request", ("Fulfil Request", "Verify Fulfilment")),
    "RIG": ("Score Risk", ("Apply Control", "Verify Control")),
    "ARA": ("Understand Request", ("Record Action", "Confirm Action")),
}


@dataclass(frozen=True, slots=True)
class StandardPhase:
    name: str
    kind: PhaseKind
    skill: str | None = None


@dataclass(frozen=True, slots=True)
class TelcoProcessProfile:
    source_id: str
    workflow_type: str
    display_name: str
    function: str
    engine: EngineCode
    phases: tuple[StandardPhase, ...]
    skills: tuple[str, ...]
    mcp_packs: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    sensor_id: str
    objective_type: str
    command_type: str
    success_event: str
    mutation_family: MutationFamily
    hitl_persona: str | None = None
    hitl_event: str | None = None


def _phase_name(skill: str) -> str:
    return " ".join(part.title() for part in skill.split("-"))


def _phases(
    engine: EngineCode,
    skills: tuple[str, ...],
    hitl_persona: str | None,
) -> tuple[StandardPhase, ...]:
    first, final = ENGINE_BOUNDARIES[engine]
    values = [StandardPhase(first, "deterministic")]
    values.extend(
        StandardPhase(_phase_name(skill), "agent", skill) for skill in skills
    )
    if hitl_persona is not None:
        values.append(StandardPhase("Authority Approval", "hitl"))
    values.extend(StandardPhase(name, "deterministic") for name in final)
    return tuple(values)


def _skills(*codes: str) -> tuple[str, ...]:
    return tuple(SKILLS_BY_CODE[code] for code in codes)


def _profile(
    source_id: str,
    workflow_type: str,
    display_name: str,
    *,
    function: str,
    engine: EngineCode,
    skills: tuple[str, ...],
    mcp_packs: tuple[str, ...],
    command_type: str,
    success_event: str,
    mutation_family: MutationFamily,
    hitl_persona: str | None = None,
) -> TelcoProcessProfile:
    return TelcoProcessProfile(
        source_id=source_id,
        workflow_type=workflow_type,
        display_name=display_name,
        function=function,
        engine=engine,
        phases=_phases(engine, skills, hitl_persona),
        skills=skills,
        mcp_packs=mcp_packs,
        allowed_tools=tuple(
            tool for pack in mcp_packs for tool in TOOLS_BY_PACK[pack]
        ),
        sensor_id=f"sensor:{workflow_type}",
        objective_type=workflow_type.replace("-", "_"),
        command_type=command_type,
        success_event=success_event,
        mutation_family=mutation_family,
        hitl_persona=hitl_persona,
        hitl_event=(
            f"{hitl_persona}_decision"
            if hitl_persona is not None
            else None
        ),
    )


_STANDARD_PROFILES = (
    _profile(
        "OSS-03",
        "ran-capacity-planning",
        "RAN Capacity Planning",
        function="network-operations",
        engine="FSP",
        skills=_skills("EC", "RIA", "SC", "NBA"),
        mcp_packs=("network", "twin"),
        command_type="approve_capacity_plan",
        success_event="capacity_plan.approved",
        mutation_family="plan",
        hitl_persona="network_ops_director",
    ),
    _profile(
        "OSS-05",
        "network-configuration-validation",
        "Network Configuration Validation",
        function="service-operations",
        engine="RIG",
        skills=_skills("EC", "RIA", "SC", "ER"),
        mcp_packs=("network", "operations", "twin"),
        command_type="record_change_validation",
        success_event="change.validation.completed",
        mutation_family="plan",
        hitl_persona="network_ops_director",
    ),
    _profile(
        "OSS-06",
        "rollout-site-planning",
        "5G and Fibre Rollout Planning",
        function="service-operations",
        engine="FSP",
        skills=_skills("SC", "NBA", "RM"),
        mcp_packs=("twin", "operations"),
        command_type="approve_rollout_plan",
        success_event="rollout.plan.approved",
        mutation_family="plan",
        hitl_persona="network_ops_director",
    ),
    _profile(
        "OSS-07",
        "network-slice-assurance",
        "Network Slice Design and Assurance",
        function="network-operations",
        engine="OFV",
        skills=_skills("RIA", "SC", "NBA", "RM"),
        mcp_packs=("network", "twin"),
        command_type="provision_network_slice",
        success_event="network_slice.assured",
        mutation_family="network",
        hitl_persona="network_ops_director",
    ),
    _profile(
        "OSS-08",
        "energy-optimization",
        "Energy and Sustainability Optimisation",
        function="network-operations",
        engine="DDA",
        skills=_skills("EC", "RIA", "NBA"),
        mcp_packs=("network", "twin"),
        command_type="apply_energy_action",
        success_event="energy.target.met",
        mutation_family="network",
    ),
    _profile(
        "OSS-10",
        "spares-inventory-optimization",
        "Spares and Inventory Optimisation",
        function="service-operations",
        engine="FSP",
        skills=_skills("EC", "RM", "NBA"),
        mcp_packs=("operations", "commercial", "twin"),
        command_type="transfer_spare_stock",
        success_event="spare_stock.rebalanced",
        mutation_family="operations",
        hitl_persona="service_ops_manager",
    ),
    _profile(
        "OSS-11",
        "site-asset-health-monitoring",
        "Site Asset Health Monitoring",
        function="network-operations",
        engine="DDA",
        skills=_skills("EC", "RIA", "NBA"),
        mcp_packs=("network", "operations"),
        command_type="prioritize_asset_work",
        success_event="asset_health.reviewed",
        mutation_family="operations",
        hitl_persona="service_ops_manager",
    ),
    _profile(
        "OSS-12",
        "backhaul-optimization",
        "Transport and Backhaul Optimisation",
        function="network-operations",
        engine="DDA",
        skills=_skills("EC", "RIA", "NBA"),
        mcp_packs=("network", "twin"),
        command_type="apply_backhaul_action",
        success_event="backhaul.stable",
        mutation_family="network",
    ),
    _profile(
        "OSS-13",
        "core-network-anomaly-management",
        "Core Network Anomaly Management",
        function="network-operations",
        engine="DDA",
        skills=_skills("EC", "RIA", "ER"),
        mcp_packs=("network", "operations"),
        command_type="execute_core_runbook",
        success_event="core_service.stable",
        mutation_family="network",
        hitl_persona="network_ops_director",
    ),
    _profile(
        "OSS-14",
        "proactive-service-assurance",
        "Proactive Service Assurance",
        function="customer-success",
        engine="DDA",
        skills=_skills("EC", "RIA", "CD"),
        mcp_packs=("network", "commercial"),
        command_type="open_proactive_assurance",
        success_event="assurance.case.opened",
        mutation_family="operations",
        hitl_persona="cs_manager",
    ),
    _profile(
        "OSS-16",
        "network-change-release",
        "Network Change and Release Orchestration",
        function="service-operations",
        engine="RIG",
        skills=_skills("RIA", "SC", "ER"),
        mcp_packs=("network", "operations", "twin"),
        command_type="advance_network_release",
        success_event="release.verified",
        mutation_family="operations",
        hitl_persona="network_ops_director",
    ),
    _profile(
        "OSS-17",
        "spectrum-interference-management",
        "Spectrum and Interference Management",
        function="network-operations",
        engine="DDA",
        skills=_skills("EC", "RIA", "NBA"),
        mcp_packs=("network", "twin"),
        command_type="apply_spectrum_action",
        success_event="interference.reduced",
        mutation_family="network",
        hitl_persona="network_ops_director",
    ),
    _profile(
        "OSS-18",
        "network-security-response",
        "Network Security Response",
        function="commercial-risk",
        engine="RIG",
        skills=_skills("EC", "RIA", "NBA"),
        mcp_packs=("network", "operations"),
        command_type="apply_security_mitigation",
        success_event="threat.contained",
        mutation_family="network",
        hitl_persona="commercial_risk_director",
    ),
    _profile(
        "OSS-19",
        "experience-benchmarking",
        "Experience Benchmarking",
        function="network-operations",
        engine="FSP",
        skills=_skills("EC", "SC", "NBA"),
        mcp_packs=("network", "twin"),
        command_type="publish_benchmark_plan",
        success_event="benchmark.plan.published",
        mutation_family="plan",
    ),
    _profile(
        "BSS-01",
        "contact-centre-agent-assist",
        "Contact Centre Agent Assist",
        function="customer-success",
        engine="ARA",
        skills=_skills("EC", "RIA", "NBA", "CD"),
        mcp_packs=("commercial", "operations", "network"),
        command_type="publish_agent_guidance",
        success_event="agent_guidance.accepted",
        mutation_family="operations",
    ),
    _profile(
        "BSS-02",
        "autonomous-self-service",
        "Autonomous Self Service",
        function="customer-success",
        engine="ARA",
        skills=_skills("EC", "PE", "ER", "CD"),
        mcp_packs=("commercial", "operations", "network"),
        command_type="execute_self_service_resolution",
        success_event="self_service.resolved",
        mutation_family="commercial",
        hitl_persona="cs_manager",
    ),
    _profile(
        "BSS-05",
        "next-best-action",
        "Next Best Action",
        function="customer-success",
        engine="ARA",
        skills=_skills("RIA", "NBA", "PE", "CD"),
        mcp_packs=("commercial", "twin"),
        command_type="issue_next_best_action",
        success_event="next_best_action.issued",
        mutation_family="commercial",
        hitl_persona="cs_manager",
    ),
    _profile(
        "BSS-07",
        "service-provisioning-activation",
        "Service Provisioning and Activation",
        function="service-operations",
        engine="OFV",
        skills=_skills("RM", "ER", "RIA"),
        mcp_packs=("commercial", "network"),
        command_type="provision_service",
        success_event="service.activated",
        mutation_family="commercial",
        hitl_persona="service_ops_manager",
    ),
    _profile(
        "BSS-08",
        "billing-dispute-resolution",
        "Billing Dispute Resolution",
        function="commercial-risk",
        engine="CTR",
        skills=_skills("EC", "PE", "ER", "CD"),
        mcp_packs=("commercial", "operations"),
        command_type="resolve_billing_dispute",
        success_event="billing_dispute.resolved",
        mutation_family="commercial",
        hitl_persona="commercial_risk_director",
    ),
    _profile(
        "BSS-09",
        "revenue-assurance",
        "Revenue Assurance",
        function="commercial-risk",
        engine="RIG",
        skills=_skills("EC", "RIA", "NBA"),
        mcp_packs=("commercial", "network"),
        command_type="apply_revenue_recovery",
        success_event="revenue_leakage.recovered",
        mutation_family="commercial",
        hitl_persona="commercial_risk_director",
    ),
    _profile(
        "BSS-10",
        "collections-dunning",
        "Collections and Dunning",
        function="commercial-risk",
        engine="RIG",
        skills=_skills("RIA", "PE", "NBA", "CD"),
        mcp_packs=("commercial",),
        command_type="apply_collections_plan",
        success_event="collections.plan.applied",
        mutation_family="commercial",
        hitl_persona="commercial_risk_director",
    ),
    _profile(
        "BSS-11",
        "fraud-prevention",
        "Fraud Prevention",
        function="commercial-risk",
        engine="RIG",
        skills=_skills("EC", "RIA", "NBA"),
        mcp_packs=("commercial", "operations"),
        command_type="apply_fraud_control",
        success_event="fraud.case.controlled",
        mutation_family="commercial",
        hitl_persona="commercial_risk_director",
    ),
    _profile(
        "BSS-12",
        "customer-onboarding-kyc",
        "Customer Onboarding and KYC",
        function="commercial-risk",
        engine="RIG",
        skills=_skills("EC", "RIA", "PE", "ER"),
        mcp_packs=("commercial", "operations"),
        command_type="complete_customer_kyc",
        success_event="customer.kyc.completed",
        mutation_family="commercial",
        hitl_persona="commercial_risk_director",
    ),
    _profile(
        "BSS-13",
        "complaint-nps-closed-loop",
        "Complaint and NPS Closed Loop",
        function="customer-success",
        engine="CTR",
        skills=_skills("EC", "RIA", "ER", "CD"),
        mcp_packs=("commercial", "operations", "network"),
        command_type="resolve_customer_complaint",
        success_event="complaint.closed",
        mutation_family="operations",
        hitl_persona="cs_manager",
    ),
    _profile(
        "BSS-14",
        "device-lifecycle-upgrade",
        "Device Lifecycle and Upgrade",
        function="customer-success",
        engine="OFV",
        skills=_skills("PE", "NBA", "RM"),
        mcp_packs=("commercial", "operations"),
        command_type="fulfil_device_upgrade",
        success_event="device_upgrade.completed",
        mutation_family="commercial",
        hitl_persona="cs_manager",
    ),
    _profile(
        "BSS-15",
        "roaming-experience-steering",
        "Roaming Experience and Steering",
        function="customer-success",
        engine="DDA",
        skills=_skills("EC", "RIA", "NBA", "CD"),
        mcp_packs=("commercial", "network"),
        command_type="apply_roaming_steer",
        success_event="roaming.experience.stable",
        mutation_family="commercial",
        hitl_persona="commercial_risk_director",
    ),
    _profile(
        "BSS-16",
        "number-sim-porting",
        "Number, SIM and Porting",
        function="service-operations",
        engine="OFV",
        skills=_skills("EC", "PE", "ER"),
        mcp_packs=("commercial", "operations"),
        command_type="complete_number_port",
        success_event="number_port.completed",
        mutation_family="commercial",
        hitl_persona="service_ops_manager",
    ),
    _profile(
        "BSS-17",
        "customer-experience-twin",
        "Customer Experience Twin",
        function="customer-success",
        engine="FSP",
        skills=_skills("EC", "RIA", "SC", "NBA"),
        mcp_packs=("commercial", "network", "twin"),
        command_type="publish_cx_experiment",
        success_event="cx_experiment.published",
        mutation_family="plan",
    ),
)

STANDARD_PROCESS_PROFILES = {
    profile.workflow_type: profile for profile in _STANDARD_PROFILES
}


def validate_process_profiles(
    profiles: dict[str, TelcoProcessProfile],
) -> None:
    for workflow_type, profile in profiles.items():
        if workflow_type != profile.workflow_type:
            raise ValueError(f"profile key mismatch: {workflow_type}")
        if profile.engine not in ENGINE_CODES:
            raise ValueError(f"{workflow_type} has unknown engine")
        if not profile.skills or not set(profile.skills) <= SKILL_NAMES:
            raise ValueError(f"{workflow_type} has invalid skills")
        if (
            not profile.mcp_packs
            or not set(profile.mcp_packs) <= set(TOOLS_BY_PACK)
        ):
            raise ValueError(f"{workflow_type} has invalid MCP packs")
        if not profile.allowed_tools:
            raise ValueError(f"{workflow_type} has no MCP tools")
        phase_skills = {
            phase.skill for phase in profile.phases if phase.kind == "agent"
        }
        if phase_skills != set(profile.skills):
            raise ValueError(f"{workflow_type} phase skills do not match")
        if (profile.hitl_persona is None) != (profile.hitl_event is None):
            raise ValueError(f"{workflow_type} has incomplete HITL metadata")


validate_process_profiles(STANDARD_PROCESS_PROFILES)

HERO_PROCESS_SUMMARIES = (
    {
        "source_id": "OSS-01",
        "workflow_type": "predictive-site-maintenance",
        "display_name": "Predictive Site Maintenance",
        "function": "network-operations",
        "maturity": "hero",
        "engine": "hero",
        "skills": ["site-failure-diagnosis"],
        "mcp_packs": ["network", "operations"],
    },
    {
        "source_id": "OSS-02",
        "workflow_type": "network-incident",
        "display_name": "Network Incident Response",
        "function": "network-operations",
        "maturity": "hero",
        "engine": "hero",
        "skills": [],
        "mcp_packs": ["network"],
    },
    {
        "source_id": "OSS-04",
        "workflow_type": "capacity-optimization",
        "display_name": "Capacity Optimisation",
        "function": "network-operations",
        "maturity": "hero",
        "engine": "hero",
        "skills": ["capacity-action-planner"],
        "mcp_packs": ["network", "twin"],
    },
    {
        "source_id": "OSS-09",
        "workflow_type": "field-repair-dispatch",
        "display_name": "Field Repair Dispatch",
        "function": "network-operations",
        "maturity": "hero",
        "engine": "hero",
        "skills": ["field-resource-matching"],
        "mcp_packs": ["operations"],
    },
    {
        "source_id": "OSS-15",
        "workflow_type": "service-ticket-resolution",
        "display_name": "Service Ticket Resolution",
        "function": "customer-success",
        "maturity": "hero",
        "engine": "hero",
        "skills": ["ticket-root-cause-correlation"],
        "mcp_packs": ["operations", "commercial", "network"],
    },
    {
        "source_id": "OSS-20",
        "workflow_type": "outage-risk-management",
        "display_name": "Outage Risk Management",
        "function": "network-operations",
        "maturity": "hero",
        "engine": "hero",
        "skills": ["outage-risk-planning"],
        "mcp_packs": ["network", "operations", "twin"],
    },
    {
        "source_id": "BSS-03",
        "workflow_type": "proactive-customer-care",
        "display_name": "Proactive Customer Care",
        "function": "customer-success",
        "maturity": "hero",
        "engine": "hero",
        "skills": [
            "proactive-customer-care-entitlement",
            "proactive-customer-care-execution",
        ],
        "mcp_packs": ["commercial", "network"],
    },
    {
        "source_id": "BSS-04",
        "workflow_type": "retention-orchestration",
        "display_name": "Retention Orchestration",
        "function": "customer-success",
        "maturity": "hero",
        "engine": "hero",
        "skills": ["churn-driver-analysis", "retention-offer-selection"],
        "mcp_packs": ["commercial", "twin"],
    },
    {
        "source_id": "BSS-06",
        "workflow_type": "order-to-activate",
        "display_name": "Order to Activate",
        "function": "network-operations",
        "maturity": "hero",
        "engine": "hero",
        "skills": [],
        "mcp_packs": ["commercial", "network"],
    },
)

STANDARD_PROCESS_SUMMARIES = tuple(
    {
        "source_id": profile.source_id,
        "workflow_type": profile.workflow_type,
        "display_name": profile.display_name,
        "function": profile.function,
        "maturity": "standard",
        "engine": profile.engine,
        "skills": list(profile.skills),
        "mcp_packs": list(profile.mcp_packs),
    }
    for profile in STANDARD_PROCESS_PROFILES.values()
)

PROCESS_LIBRARY = tuple(
    sorted(
        (*HERO_PROCESS_SUMMARIES, *STANDARD_PROCESS_SUMMARIES),
        key=lambda item: (
            0 if str(item["source_id"]).startswith("OSS") else 1,
            str(item["source_id"]),
        ),
    )
)
