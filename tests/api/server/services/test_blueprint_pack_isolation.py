from __future__ import annotations

from api.server.services.blueprint_inventory import composition_tree
from api.shared.vertical_loader import build_runtime


TELCO_WORKFLOWS = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
}
TELCO_SKILLS = {
    "proactive-customer-care-entitlement",
    "proactive-customer-care-execution",
}


def test_telco_blueprint_inventory_is_pack_local(tmp_path) -> None:
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    tree = composition_tree(runtime)

    assert {
        domain["workflow_type"] for domain in tree["domains"]
    } == TELCO_WORKFLOWS
    assert {skill["name"] for skill in tree["skills"]} == TELCO_SKILLS
    assert {mcp["name"] for mcp in tree["mcps"]} == {"customer_care"}
    assert tree["meta_skills"] == []
    assert tree["vertical"]["name"] == "telco"
    assert all(domain["status"] == "live" for domain in tree["domains"])


def test_agency_blueprint_inventory_excludes_telco(tmp_path) -> None:
    runtime = build_runtime({}, data_root=tmp_path)

    tree = composition_tree(runtime)

    assert TELCO_WORKFLOWS.isdisjoint(
        domain["workflow_type"] for domain in tree["domains"]
    )
    assert TELCO_SKILLS.isdisjoint(
        skill["name"] for skill in tree["skills"]
    )
    assert "customer_care" not in {
        mcp["name"] for mcp in tree["mcps"]
    }
    assert {"Onboarding", "Procurement", "Legal", "IT"} <= {
        domain["name"] for domain in tree["domains"]
    }
    assert tree["meta_skills"]
    assert tree["vertical"]["name"] == "agency"
