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
TELCO_CUSTOMER_SUCCESS_SURFACE = "customer-success"
TELCO_CUSTOMER_SUCCESS_KPIS = (
    "nps",
    "proactive-resolution-pct",
    "credit-cost",
)
TELCO_ONLY_AUTHORITY_ROLES = {
    "cs_director",
    "cs_account_director",
    "cs_manager",
    "cs_specialist",
}
TELCO_AUTHORITY_ROLES = TELCO_ONLY_AUTHORITY_ROLES | {"delivery_lead"}
TELCO_PERSONA_ROLES = TELCO_AUTHORITY_ROLES


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
import sys
from api.shared.agents import AGENTS
from api.shared.authority import AUTHORITY
from api.shared.domains import DOMAINS
from api.shared.functions import FUNCTIONS
from api.shared.personas import PERSONAS
print(json.dumps({
    "agents": sorted(AGENTS),
    "authority": sorted(AUTHORITY),
    "domains": sorted(DOMAINS),
    "functions": sorted(FUNCTIONS),
    "personas": sorted(PERSONAS),
    "modules": sorted(sys.modules),
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


TELCO_FUNCTIONS_SCRIPT = """
import json
from verticals.telco.functions import TELCO_FUNCTIONS
fn = TELCO_FUNCTIONS["customer-success"]
print(json.dumps({
    "operator_surface": fn.operator_surface,
    "kpis": fn.kpis,
}))
"""


def _telco_functions_snapshot() -> dict:
    environment = os.environ.copy()
    environment.pop("ZAVA_WORLD", None)
    environment.pop("ZAVA_WORLD_SCALE", None)
    environment["ZAVA_VERTICAL"] = "telco"
    result = subprocess.run(
        [sys.executable, "-c", TELCO_FUNCTIONS_SCRIPT],
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
    assert TELCO_ONLY_AUTHORITY_ROLES.isdisjoint(agency["authority"])
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
    assert set(telco["authority"]) == TELCO_AUTHORITY_ROLES
    assert set(telco["personas"]) == {
        "cs_director",
        "cs_account_director",
        "cs_manager",
        "cs_specialist",
        "delivery_lead",
    }


def test_agency_process_never_imports_telco_domain_or_function_modules() -> None:
    """Importing the shared compatibility adapters under the default (Agency)
    vertical must not pull `verticals.telco.domains` / `verticals.telco.functions`
    into `sys.modules`, and must expose no Telco workflow/function IDs."""
    agency = _registry_snapshot(None)

    assert "verticals.telco.domains" not in agency["modules"]
    assert "verticals.telco.functions" not in agency["modules"]
    assert "verticals.agency.domains" in agency["modules"]
    assert "verticals.agency.functions" in agency["modules"]
    assert TELCO_WORKFLOWS.isdisjoint(agency["domains"])
    assert TELCO_FUNCTIONS.isdisjoint(agency["functions"])


def test_telco_process_never_imports_agency_domain_or_function_modules() -> None:
    """Importing the shared compatibility adapters under ZAVA_VERTICAL=telco
    must not pull `verticals.agency.domains` / `verticals.agency.functions`
    into `sys.modules`, and must expose only the Telco workflow/function IDs."""
    telco = _registry_snapshot("telco")

    assert "verticals.agency.domains" not in telco["modules"]
    assert "verticals.agency.functions" not in telco["modules"]
    assert "verticals.telco.domains" in telco["modules"]
    assert "verticals.telco.functions" in telco["modules"]
    assert set(telco["domains"]) == TELCO_WORKFLOWS
    assert set(telco["functions"]) == TELCO_FUNCTIONS


def test_agency_process_never_imports_telco_agent_authority_or_persona_modules() -> None:
    """Importing the shared compatibility adapters under the default (Agency)
    vertical must not pull `verticals.telco.agents` / `verticals.telco.authority`
    / `verticals.telco.personas` into `sys.modules`, and must expose no
    Telco-only agent/authority/persona IDs."""
    agency = _registry_snapshot(None)

    assert "verticals.telco.agents" not in agency["modules"]
    assert "verticals.telco.authority" not in agency["modules"]
    assert "verticals.telco.personas" not in agency["modules"]
    assert "verticals.agency.agents" in agency["modules"]
    assert "verticals.agency.authority" in agency["modules"]
    assert "verticals.agency.personas" in agency["modules"]
    assert TELCO_AGENTS.isdisjoint(agency["agents"])
    assert TELCO_ONLY_AUTHORITY_ROLES.isdisjoint(agency["authority"])
    assert TELCO_ONLY_AUTHORITY_ROLES.isdisjoint(agency["personas"])
    # kernel identity + Agency's own delivery_lead remain present
    assert "reflector.entity_reflector" in agency["agents"]
    assert "delivery_lead" in agency["authority"]
    assert "delivery_lead" in agency["personas"]


def test_telco_process_never_imports_agency_agent_authority_or_persona_modules() -> None:
    """Importing the shared compatibility adapters under ZAVA_VERTICAL=telco
    must not pull `verticals.agency.agents` / `verticals.agency.authority`
    / `verticals.agency.personas` into `sys.modules`, and must expose only
    Telco agent/authority/persona IDs (plus the kernel identity actor)."""
    telco = _registry_snapshot("telco")

    assert "verticals.agency.agents" not in telco["modules"]
    assert "verticals.agency.authority" not in telco["modules"]
    assert "verticals.agency.personas" not in telco["modules"]
    assert "verticals.telco.agents" in telco["modules"]
    assert "verticals.telco.authority" in telco["modules"]
    assert "verticals.telco.personas" in telco["modules"]
    assert set(telco["agents"]) == TELCO_AGENTS | {"reflector.entity_reflector"}
    assert set(telco["authority"]) == TELCO_AUTHORITY_ROLES
    assert set(telco["personas"]) == TELCO_PERSONA_ROLES


def test_shared_adapters_do_not_call_selection_parsing_directly() -> None:
    """The shared compatibility adapters (agents/authority/personas) must
    source their registries exclusively through
    `api.shared.vertical_loader.active_runtime()` — never by calling
    `select_vertical`/parsing `os.environ` themselves. A regression back to
    per-module environment parsing would reintroduce the
    filtering-from-superset anti-pattern this task removes."""
    import ast
    import inspect

    import api.shared.agents as agents_module
    import api.shared.authority as authority_module
    import api.shared.personas as personas_module

    for module in (agents_module, authority_module, personas_module):
        source = inspect.getsource(module)
        tree = ast.parse(source)
        assert "os" not in {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }, f"{module.__name__} must not import os directly"
        assert "select_vertical" not in source, (
            f"{module.__name__} must not call select_vertical() itself; "
            "it must source data through active_runtime()"
        )


def test_telco_customer_success_pack_local_metadata_is_exact() -> None:
    snapshot = _telco_functions_snapshot()

    assert snapshot["operator_surface"] == TELCO_CUSTOMER_SUCCESS_SURFACE
    assert tuple(snapshot["kpis"]) == TELCO_CUSTOMER_SUCCESS_KPIS


IMPORT_SMOKE_SCRIPT = """
import api.shared.agents
import api.shared.authority
import api.shared.domains
import api.shared.functions
import api.shared.personas
print("ok")
"""


def _import_smoke(vertical: str | None) -> None:
    environment = os.environ.copy()
    if vertical is None:
        environment.pop("ZAVA_VERTICAL", None)
    else:
        environment["ZAVA_VERTICAL"] = vertical
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_SMOKE_SCRIPT],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "ok"


def test_import_smoke_default_vertical() -> None:
    _import_smoke(None)


def test_import_smoke_agency_vertical() -> None:
    _import_smoke("agency")


def test_import_smoke_telco_vertical() -> None:
    _import_smoke("telco")


def test_telco_server_imports_no_agency_ambient_modules(tmp_path) -> None:
    environment = os.environ.copy()
    environment["ZAVA_VERTICAL"] = "telco"
    environment["ENTITY_PLANE_ENABLED"] = "0"
    environment["PORTAL_DATA_DIR"] = str(tmp_path)
    script = """
import json
import sys
import api.server.main
print(json.dumps(sorted(
    name for name in sys.modules
    if name.startswith("api.server.services.ambient_agents")
)))
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout.splitlines()[-1]) == []
