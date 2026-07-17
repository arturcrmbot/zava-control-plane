from __future__ import annotations

from api.shared.vertical_loader import build_runtime
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES


HERO_WORKFLOWS = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
    "outage-risk-management",
    "predictive-site-maintenance",
    "field-repair-dispatch",
    "capacity-optimization",
    "service-ticket-resolution",
    "retention-orchestration",
}
EXPECTED_WORKFLOWS = HERO_WORKFLOWS | set(STANDARD_PROCESS_PROFILES)
NETWORK_WORKFLOWS = {
    "network-incident",
    "order-to-activate",
    "outage-risk-management",
    "predictive-site-maintenance",
    "field-repair-dispatch",
    "capacity-optimization",
} | {
    profile.workflow_type
    for profile in STANDARD_PROCESS_PROFILES.values()
    if profile.function == "network-operations"
}
CUSTOMER_WORKFLOWS = {
    "proactive-customer-care",
    "service-ticket-resolution",
    "retention-orchestration",
} | {
    profile.workflow_type
    for profile in STANDARD_PROCESS_PROFILES.values()
    if profile.function == "customer-success"
}
SERVICE_WORKFLOWS = {
    profile.workflow_type
    for profile in STANDARD_PROCESS_PROFILES.values()
    if profile.function == "service-operations"
}
COMMERCIAL_RISK_WORKFLOWS = {
    profile.workflow_type
    for profile in STANDARD_PROCESS_PROFILES.values()
    if profile.function == "commercial-risk"
}
NEW_OBJECTIVES = {
    "outage_prevention",
    "site_maintenance",
    "field_repair",
    "capacity_recovery",
    "ticket_resolution",
    "customer_retention",
}


def test_telco_pack_declares_37_live_workflows(tmp_path):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    assert set(runtime.pack.domains) == EXPECTED_WORKFLOWS
    assert all(not domain.stub for domain in runtime.pack.domains.values())
    assert {
        domain.orchestrator_name for domain in runtime.pack.domains.values()
    } <= runtime.pack.durable_functions.orchestrators


def test_telco_functions_own_the_cascade_domains(tmp_path):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    functions = runtime.pack.organisation_functions
    assert set(functions["network-operations"].owns_domains) == NETWORK_WORKFLOWS
    assert set(functions["customer-success"].owns_domains) == CUSTOMER_WORKFLOWS
    assert set(functions["service-operations"].owns_domains) == SERVICE_WORKFLOWS
    assert (
        set(functions["commercial-risk"].owns_domains)
        == COMMERCIAL_RISK_WORKFLOWS
    )
    assert functions["network-operations"].persona_hierarchy.role == (
        "network_ops_director"
    )
    assert functions["network-operations"].persona_hierarchy.manages[0].role == (
        "delivery_lead"
    )


def test_telco_world_routes_every_new_objective(tmp_path):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )
    world = runtime.pack.worlds["telco"]

    routes = {route.objective_type: route for route in world.objective_routes}
    assert NEW_OBJECTIVES <= set(routes)
    assert set(world.responders) >= NEW_OBJECTIVES
    assert {
        responder.workflow_type
        for responder in world.responders.values()
    } == HERO_WORKFLOWS


def test_telco_authority_chain_stays_inside_pack(tmp_path):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    authority = runtime.pack.authority
    assert authority["delivery_lead"].delegate_to == "network_ops_director"
    assert authority["network_ops_director"].delegate_to is None
    assert authority["network_ops_director"].spend_limit_gbp == 1_000_000.0
    assert "network_ops_director" in runtime.pack.personas
