"""verticals/telco/domains.py — Telco vertical domain registry.

Canonical Telco ``Domain`` declarations. Agency's domains live in
``verticals/agency/domains.py`` and are never imported here.

Function back-references are wired once, at
``verticals.telco.manifest.build_pack()`` time, via
``verticals._helpers.wire_domain_functions`` — this module declares no
back-refs and performs no boot-time mutation.
"""
from __future__ import annotations

from api.shared.domain_contracts import Domain, HitlGate, Phase
from verticals.telco.process_profiles import (
    STANDARD_PROCESS_PROFILES,
    TelcoProcessProfile,
)


HERO_DOMAINS: dict[str, Domain] = {
    # ----- telco: network-incident response (actor-world scenario) -----
    # Autonomous, reversible mitigation — NO HITL gate by explicit design
    # (see docs/superpowers/specs/network-incident-brief.yaml). The primary
    # live trigger is the actor-world network.anomaly sensor bridged to
    # NetworkIncidentOrchestrator; the spawn_fn lets the simulator schedule
    # it too. Owned by the ops function (incident-rate KPI).
    #
    # All four phases are DETERMINISTIC: the orchestrator runs two real
    # deterministic activities (network_incident_impact_activity +
    # network_incident_reroute_activity) between the bridge-side telemetry
    # correlation and the later world-evaluation recovery verification. There
    # are no agent/GHCP skills — ``skills`` is intentionally empty; the greedy
    # reroute is pure deterministic code, not a reasoning model.
    "network-incident": Domain(
        workflow_type="network-incident",
        display_name="Network Incident Response",
        workflow_id_prefix="NIR",
        orchestrator_name="NetworkIncidentOrchestrator",
        operator_surface="network-operations",
        phases=(
            Phase("Telemetry Correlation", "deterministic"),
            Phase("Impact Diagnosis", "deterministic"),
            Phase("Reroute Planning", "deterministic"),
            Phase("Recovery Verification", "deterministic"),
        ),
        hitl_gates=(),
        skills=(),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_network_incident_workflow",
        # Cell-site incidents are frequent in a large RAN — cap at every
        # 900s (15 min) of demo-warped time.
        realistic_interval_seconds=900,
    ),
    "proactive-customer-care": Domain(
        workflow_type="proactive-customer-care",
        display_name="Proactive Customer Care",
        workflow_id_prefix="CARE",
        orchestrator_name="ProactiveCustomerCareOrchestrator",
        operator_surface="customer-success",
        phases=(
            Phase("Impact Assessment", "deterministic"),
            Phase("Entitlement Decision", "agent"),
            Phase("Credit Approval", "hitl"),
            Phase("Care Execution", "agent"),
            Phase("Outcome Verification", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Credit Approval",
                "cs_manager_decision",
                "cs_manager",
                wait_probability=0.0,
            ),
        ),
        skills=(
            "proactive-customer-care-entitlement",
            "proactive-customer-care-execution",
        ),
        spawn_fn="api.server.services.simulator_orchestrator.spawn_proactive_customer_care_workflow",
        realistic_interval_seconds=86400,
    ),
    "order-to-activate": Domain(
        workflow_type="order-to-activate",
        display_name="Order to Activate",
        workflow_id_prefix="ORDER",
        orchestrator_name="OrderToActivateOrchestrator",
        operator_surface="service-fulfillment",
        phases=(
            Phase("Order Intake", "deterministic"),
            Phase("Feasibility Check", "deterministic"),
            Phase("Capacity Approval", "hitl"),
            Phase("Service Activation", "deterministic"),
            Phase("Activation Verification", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Capacity Approval",
                "capacity_manager_decision",
                "delivery_lead",
                wait_probability=0.0,
            ),
        ),
        skills=(),
        spawn_fn=None,
        realistic_interval_seconds=86400,
    ),
    "outage-risk-management": Domain(
        workflow_type="outage-risk-management",
        display_name="Outage Risk Management",
        workflow_id_prefix="OUTAGE",
        orchestrator_name="OutageRiskManagementOrchestrator",
        operator_surface="network-operations",
        phases=(
            Phase("Assess Weather Risk", "deterministic"),
            Phase("Plan Pre-Staging", "agent"),
            Phase("Approve Exceptional Spend", "hitl"),
            Phase("Pre-Stage Resources", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Approve Exceptional Spend",
                "network_ops_director_decision",
                "network_ops_director",
                wait_probability=0.0,
            ),
        ),
        skills=("outage-risk-planning",),
        realistic_interval_seconds=86_400,
    ),
    "predictive-site-maintenance": Domain(
        workflow_type="predictive-site-maintenance",
        display_name="Predictive Site Maintenance",
        workflow_id_prefix="MAINT",
        orchestrator_name="PredictiveSiteMaintenanceOrchestrator",
        operator_surface="network-operations",
        phases=(
            Phase("Diagnose Failure Risk", "agent"),
            Phase("Plan Maintenance", "deterministic"),
            Phase("Approve Replacement", "hitl"),
            Phase("Create Work Order", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Approve Replacement",
                "network_ops_director_decision",
                "network_ops_director",
                wait_probability=0.0,
            ),
        ),
        skills=("site-failure-diagnosis",),
        realistic_interval_seconds=86_400,
    ),
    "field-repair-dispatch": Domain(
        workflow_type="field-repair-dispatch",
        display_name="Field Repair Dispatch",
        workflow_id_prefix="FIELD",
        orchestrator_name="FieldRepairDispatchOrchestrator",
        operator_surface="network-operations",
        phases=(
            Phase("Match Field Resources", "agent"),
            Phase("Validate Dispatch", "deterministic"),
            Phase("Approve Dispatch Exception", "hitl"),
            Phase("Dispatch Repair", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Approve Dispatch Exception",
                "delivery_lead_decision",
                "delivery_lead",
                wait_probability=0.0,
            ),
        ),
        skills=("field-resource-matching",),
        realistic_interval_seconds=3_600,
    ),
    "capacity-optimization": Domain(
        workflow_type="capacity-optimization",
        display_name="Capacity Optimization",
        workflow_id_prefix="CAP",
        orchestrator_name="CapacityOptimizationOrchestrator",
        operator_surface="network-operations",
        phases=(
            Phase("Diagnose Congestion", "deterministic"),
            Phase("Plan Capacity Action", "agent"),
            Phase("Approve Capital Action", "hitl"),
            Phase("Apply Capacity Action", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Approve Capital Action",
                "network_ops_director_decision",
                "network_ops_director",
                wait_probability=0.0,
            ),
        ),
        skills=("capacity-action-planner",),
        realistic_interval_seconds=86_400,
    ),
    "service-ticket-resolution": Domain(
        workflow_type="service-ticket-resolution",
        display_name="Service Ticket Resolution",
        workflow_id_prefix="TICKET",
        orchestrator_name="ServiceTicketResolutionOrchestrator",
        operator_surface="customer-success",
        phases=(
            Phase("Correlate Root Cause", "agent"),
            Phase("Plan Ticket Resolution", "deterministic"),
            Phase("Review Vulnerable Customers", "hitl"),
            Phase("Resolve Ticket Batch", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Review Vulnerable Customers",
                "cs_manager_decision",
                "cs_manager",
                wait_probability=0.0,
            ),
        ),
        skills=("ticket-root-cause-correlation",),
        realistic_interval_seconds=3_600,
    ),
    "retention-orchestration": Domain(
        workflow_type="retention-orchestration",
        display_name="Retention Orchestration",
        workflow_id_prefix="RETAIN",
        orchestrator_name="RetentionOrchestrationOrchestrator",
        operator_surface="customer-success",
        phases=(
            Phase("Analyse Churn Drivers", "agent"),
            Phase("Select Retention Offer", "agent"),
            Phase("Approve High-Value Offer", "hitl"),
            Phase("Issue Retention Offer", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Approve High-Value Offer",
                "cs_manager_decision",
                "cs_manager",
                wait_probability=0.0,
            ),
        ),
        skills=("churn-driver-analysis", "retention-offer-selection"),
        realistic_interval_seconds=86_400,
    ),
}

ENGINE_ORCHESTRATORS = {
    "DDA": "TelcoDetectDiagnoseActOrchestrator",
    "FSP": "TelcoForecastSimulatePlanOrchestrator",
    "CTR": "TelcoCaseTriageResolveOrchestrator",
    "OFV": "TelcoOrderFulfilVerifyOrchestrator",
    "RIG": "TelcoRiskInvestigateGovernOrchestrator",
    "ARA": "TelcoAssistRecommendActOrchestrator",
}


def _domain_from_profile(profile: TelcoProcessProfile) -> Domain:
    gates: tuple[HitlGate, ...] = ()
    if profile.hitl_persona and profile.hitl_event:
        hitl_phase = next(
            phase.name for phase in profile.phases if phase.kind == "hitl"
        )
        gates = (
            HitlGate(
                hitl_phase,
                profile.hitl_event,
                profile.hitl_persona,
                wait_probability=0.0,
            ),
        )
    return Domain(
        workflow_type=profile.workflow_type,
        display_name=profile.display_name,
        workflow_id_prefix=profile.source_id.replace("-", ""),
        orchestrator_name=ENGINE_ORCHESTRATORS[profile.engine],
        operator_surface=profile.function,
        phases=tuple(Phase(phase.name, phase.kind) for phase in profile.phases),
        hitl_gates=gates,
        skills=profile.skills,
        realistic_interval_seconds=86_400,
    )


STANDARD_DOMAINS = {
    workflow_type: _domain_from_profile(profile)
    for workflow_type, profile in STANDARD_PROCESS_PROFILES.items()
}
TELCO_DOMAINS: dict[str, Domain] = {
    **HERO_DOMAINS,
    **STANDARD_DOMAINS,
}
