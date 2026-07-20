import json
import os
import subprocess
import sys

from api.server.routes.runtime import runtime_payload
from api.server.services.event_bus import EventBus
from api.server.world.service import ActorWorldService
from api.shared.vertical_loader import build_runtime
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


def test_fashion_runtime_payload_exposes_pack_owned_ui_and_world(tmp_path) -> None:
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    )

    payload = runtime_payload(runtime)

    assert payload["vertical"] == {
        "name": "fashion",
        "display_name": "Fashion Retail",
        "manifest_version": "1",
        "fingerprint": "fashion:1",
    }
    assert payload["world"] == "fashion"
    assert payload["world_scale"] == "demo"
    assert payload["capabilities"] == [
        "blueprint",
        "knowledge",
        "memory",
        "world",
    ]
    assert payload["ui"] == {
        "lenses": [
            "process-library",
            "order",
            "customer-impact",
            "control",
        ],
        "theme": {"accent": "#ec4899", "label": "Fashion Retail"},
    }


def test_fashion_actor_world_installs_through_the_shared_runtime(tmp_path) -> None:
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    )

    service = ActorWorldService.for_runtime(
        runtime,
        seed=20260720,
        bus=EventBus(),
    )

    assert service.scenario_name == "fashion"
    assert service.scale_name == "demo"
    assert len(service.scenario.stores) == 8
    assert len(service.scenario.skus) == 192


def test_fashion_process_imports_only_fashion_business_modules() -> None:
    environment = os.environ.copy()
    environment["ZAVA_VERTICAL"] = "fashion"
    script = """
import json
import sys
from api.shared.agents import AGENTS
from api.shared.domains import DOMAINS
from api.shared.functions import FUNCTIONS
from api.shared.personas import PERSONAS
print(json.dumps({
    "agents": sorted(AGENTS),
    "domains": sorted(DOMAINS),
    "functions": sorted(FUNCTIONS),
    "personas": sorted(PERSONAS),
    "modules": sorted(sys.modules),
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    snapshot = json.loads(result.stdout)

    assert set(snapshot["domains"]) == set(FASHION_PROCESS_PROFILES)
    assert set(snapshot["functions"]) == {
        "merchandising-planning",
        "supply-chain-fulfilment",
        "marketplace-operations",
        "customer-returns",
    }
    assert "verticals.agency.domains" not in snapshot["modules"]
    assert "verticals.telco.domains" not in snapshot["modules"]
    assert all(
        not module.startswith(("verticals.agency.", "verticals.telco."))
        for module in snapshot["modules"]
    )


def test_fashion_function_app_registers_only_fashion_orchestrators() -> None:
    environment = os.environ.copy()
    environment["ZAVA_VERTICAL"] = "fashion"
    # Disable the entity plane so the subprocess does not compete for the
    # KuzuDB file lock with the parent pytest process (which holds the lock
    # whenever any test in the session has imported api.server.state).
    environment["ENTITY_PLANE_ENABLED"] = "0"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, function_app;"
                "print(json.dumps(sorted("
                "f.get_function_name() for f in function_app.app.get_functions()"
                ")))"
            ),
        ],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    names = set(json.loads(result.stdout.splitlines()[-1]))
    expected = {
        profile.orchestrator_name
        for profile in FASHION_PROCESS_PROFILES.values()
    } | {
        "fashion_skill_activity_trigger",
        "fashion_command_activity_trigger",
    }

    assert expected <= names
    assert "NetworkIncidentOrchestrator" not in names
    assert "ExpenseClaimOrchestrator" not in names
