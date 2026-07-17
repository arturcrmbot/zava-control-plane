from __future__ import annotations

from api.shared.vertical_loader import build_runtime


EXPECTED_WORKFLOWS = {
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
NETWORK_WORKFLOWS = {
    "network-incident",
    "order-to-activate",
    "outage-risk-management",
    "predictive-site-maintenance",
    "field-repair-dispatch",
    "capacity-optimization",
}
CUSTOMER_WORKFLOWS = {
    "proactive-customer-care",
    "service-ticket-resolution",
    "retention-orchestration",
}
NEW_OBJECTIVES = {
    "outage_prevention",
    "site_maintenance",
    "field_repair",
    "capacity_recovery",
    "ticket_resolution",
    "customer_retention",
}


def test_telco_pack_declares_nine_live_workflows(tmp_path):
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
    } == EXPECTED_WORKFLOWS


def test_telco_authority_chain_stays_inside_pack(tmp_path):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    authority = runtime.pack.authority
    assert authority["delivery_lead"].delegate_to == "network_ops_director"
    assert authority["network_ops_director"].delegate_to is None
    assert "network_ops_director" in runtime.pack.personas
