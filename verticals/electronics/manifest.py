from __future__ import annotations

from importlib import import_module
from pathlib import Path

from api.shared.vertical_pack import (
    DurableFunctionRegistration,
    LifecycleRegistration,
    RecordingSources,
    SeedRegistration,
    VerticalPack,
)
from verticals._helpers import load_ui_manifest, wire_domain_functions
from verticals.electronics.agents import ELECTRONICS_AGENTS
from verticals.electronics.authority import ELECTRONICS_AUTHORITY
from verticals.electronics.domains import ELECTRONICS_DOMAINS
from verticals.electronics.functions import ELECTRONICS_FUNCTIONS
from verticals.electronics.lifecycle import bootstrap, start
from verticals.electronics.personas import ELECTRONICS_PERSONAS
from verticals.electronics.projections import ELECTRONICS_PROJECTIONS
from verticals.electronics.process_profiles import ELECTRONICS_PROCESS_PROFILES
from verticals.electronics.worlds import ELECTRONICS_WORLDS


PACK_ROOT = Path(__file__).resolve().parent


def _load_durable_module():
    return import_module("verticals.electronics.durable")


def build_pack() -> VerticalPack:
    domains = wire_domain_functions(
        dict(ELECTRONICS_DOMAINS),
        dict(ELECTRONICS_FUNCTIONS),
    )
    return VerticalPack(
        root=PACK_ROOT,
        name="electronics",
        display_name="Electronics Retail",
        manifest_version="1",
        domains=domains,
        organisation_functions=ELECTRONICS_FUNCTIONS,
        agents=ELECTRONICS_AGENTS,
        authority=ELECTRONICS_AUTHORITY,
        personas=ELECTRONICS_PERSONAS,
        policy_sources=(PACK_ROOT / "policies" / "tools.yaml",),
        durable_functions=DurableFunctionRegistration(
            load_module=_load_durable_module,
            orchestrators=frozenset(
                profile.orchestrator
                for profile in ELECTRONICS_PROCESS_PROFILES.values()
            ),
            activities=frozenset(
                {
                    "electronics_evidence_activity_trigger",
                    "electronics_decision_activity_trigger",
                    "electronics_command_activity_trigger",
                }
            ),
        ),
        personae_roots=(PACK_ROOT / "personae",),
        skill_roots=(PACK_ROOT / "skills",),
        mcp_modules=("verticals.electronics.mcp_tools.retail",),
        external_capabilities=frozenset({"authority_check"}),
        worlds=ELECTRONICS_WORLDS,
        default_world="electronics",
        seed=SeedRegistration(bootstrap=bootstrap),
        projections=ELECTRONICS_PROJECTIONS,
        memory_workflow_types=tuple(domains),
        lifecycle=LifecycleRegistration(start=start),
        recordings=RecordingSources(
            curated_dirs=(PACK_ROOT / "recordings",)
        ),
        ui=load_ui_manifest(PACK_ROOT / "ui.json"),
        ramp_workflow_types=(),
    )

