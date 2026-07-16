from __future__ import annotations

import json
import os
import subprocess
import sys

from api.shared.vertical_loader import build_runtime


TELCO_WORKFLOWS = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
}
TELCO_AGENTS = {
    "proactive-customer-care-entitlement",
    "proactive-customer-care-execution",
}
AGENCY_FUNCTIONS = {
    "finance",
    "hr",
    "revenue",
    "ops",
    "legal",
    "marketing",
    "tech",
    "data",
    "ceo",
    "legacy",
}
TELCO_FUNCTIONS = {"network-operations", "customer-success"}


def test_agency_default_excludes_all_telco_business_assets(tmp_path) -> None:
    runtime = build_runtime({}, data_root=tmp_path)

    assert runtime.pack.name == "agency"
    assert TELCO_WORKFLOWS.isdisjoint(runtime.pack.domains)
    assert TELCO_AGENTS.isdisjoint(runtime.pack.agents)
    assert set(runtime.pack.organisation_functions) == AGENCY_FUNCTIONS
    assert "telco" not in runtime.pack.worlds
    assert all(
        "telco" not in str(path).lower()
        for path in runtime.pack.recordings.curated_dirs
    )


def test_telco_contains_only_the_proven_business_slice(tmp_path) -> None:
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    assert set(runtime.pack.domains) == TELCO_WORKFLOWS
    assert set(runtime.pack.agents) == TELCO_AGENTS
    assert set(runtime.pack.organisation_functions) == TELCO_FUNCTIONS
    assert set(runtime.pack.worlds) == {"telco"}
    assert runtime.world_name == "telco"
    assert runtime.world_scale_name == "demo"
    assert runtime.pack.ramp_workflow_types == ()


REGISTRY_SCRIPT = """
import json
from api.shared.agents import AGENTS
from api.shared.domains import DOMAINS
from api.shared.functions import FUNCTIONS
from api.shared.personas import PERSONAS
print(json.dumps({
    "agents": sorted(AGENTS),
    "domains": sorted(DOMAINS),
    "functions": sorted(FUNCTIONS),
    "personas": sorted(PERSONAS),
}))
"""


def _registry_snapshot(vertical: str | None) -> dict:
    environment = os.environ.copy()
    environment.pop("ZAVA_WORLD", None)
    environment.pop("ZAVA_WORLD_SCALE", None)
    if vertical is None:
        environment.pop("ZAVA_VERTICAL", None)
    else:
        environment["ZAVA_VERTICAL"] = vertical
    result = subprocess.run(
        [sys.executable, "-c", REGISTRY_SCRIPT],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_compatibility_registries_expose_only_active_pack_plus_kernel() -> None:
    agency = _registry_snapshot(None)
    telco = _registry_snapshot("telco")

    assert TELCO_WORKFLOWS.isdisjoint(agency["domains"])
    assert TELCO_AGENTS.isdisjoint(agency["agents"])
    assert set(agency["functions"]) == AGENCY_FUNCTIONS
    assert {
        "cs_director",
        "cs_account_director",
        "cs_manager",
        "cs_specialist",
    }.isdisjoint(agency["personas"])
    assert set(telco["domains"]) == TELCO_WORKFLOWS
    assert set(telco["functions"]) == TELCO_FUNCTIONS
    assert set(telco["agents"]) == TELCO_AGENTS | {
        "reflector.entity_reflector"
    }
    assert set(telco["personas"]) == {
        "cs_director",
        "cs_account_director",
        "cs_manager",
        "cs_specialist",
        "delivery_lead",
    }
