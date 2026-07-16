"""verticals/telco/domains.py — Telco vertical domain registry.

Canonical Telco ``Domain`` declarations. The Telco pack owns exactly three
workflow types: ``network-incident``, ``proactive-customer-care``, and
``order-to-activate``. Agency's domains live in
``verticals/agency/domains.py`` and are never imported here.

Function back-references are wired once, at
``verticals.telco.manifest.build_pack()`` time, via
``verticals._helpers.wire_domain_functions`` — this module declares no
back-refs and performs no boot-time mutation.
"""
from __future__ import annotations

from api.shared.domain_contracts import Domain, HitlGate, Phase


TELCO_DOMAINS: dict[str, Domain] = {
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
}
