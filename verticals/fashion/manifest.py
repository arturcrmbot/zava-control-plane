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
from verticals.fashion.agents import FASHION_AGENTS
from verticals.fashion.authority import FASHION_AUTHORITY
from verticals.fashion.domains import FASHION_DOMAINS
from verticals.fashion.functions import FASHION_FUNCTIONS
from verticals.fashion.lifecycle import bootstrap, start
from verticals.fashion.personas import FASHION_PERSONAS
from verticals.fashion.projections import FASHION_PROJECTIONS
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.worlds import FASHION_WORLDS


PACK_ROOT = Path(__file__).resolve().parent


def _load_durable_module():
    return import_module("verticals.fashion.durable")


def build_pack() -> VerticalPack:
    domains = wire_domain_functions(
        dict(FASHION_DOMAINS),
        dict(FASHION_FUNCTIONS),
    )
    return VerticalPack(
        root=PACK_ROOT,
        name="fashion",
        display_name="Fashion Retail",
        manifest_version="2",
        domains=domains,
        organisation_functions=FASHION_FUNCTIONS,
        agents=FASHION_AGENTS,
        authority=FASHION_AUTHORITY,
        personas=FASHION_PERSONAS,
        policy_sources=(PACK_ROOT / "policies" / "tools.yaml",),
        durable_functions=DurableFunctionRegistration(
            load_module=_load_durable_module,
            orchestrators=frozenset(
                profile.orchestrator
                for profile in FASHION_PROCESS_PROFILES.values()
            ),
            activities=frozenset(
                {
                    "fashion_evidence_activity_trigger",
                    "fashion_decision_activity_trigger",
                    "fashion_command_activity_trigger",
                }
            ),
        ),
        personae_roots=(PACK_ROOT / "personae",),
        skill_roots=(PACK_ROOT / "skills",),
        mcp_modules=("verticals.fashion.mcp_tools.retail",),
        external_capabilities=frozenset({"authority_check"}),
        worlds=FASHION_WORLDS,
        default_world="fashion",
        seed=SeedRegistration(bootstrap=bootstrap),
        projections=FASHION_PROJECTIONS,
        memory_workflow_types=tuple(domains),
        lifecycle=LifecycleRegistration(start=start),
        recordings=RecordingSources(
            curated_dirs=(PACK_ROOT / "recordings",)
        ),
        ui=load_ui_manifest(PACK_ROOT / "ui.json"),
        ramp_workflow_types=(),
    )

