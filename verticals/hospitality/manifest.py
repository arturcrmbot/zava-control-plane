"""Sole composition root for the Hospitality vertical pack."""
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
from verticals.hospitality.agents import HOSPITALITY_AGENTS
from verticals.hospitality.authority import HOSPITALITY_AUTHORITY
from verticals.hospitality.domains import HOSPITALITY_DOMAINS
from verticals.hospitality.functions import HOSPITALITY_FUNCTIONS
from verticals.hospitality.lifecycle import bootstrap, start
from verticals.hospitality.personas import HOSPITALITY_PERSONAS
from verticals.hospitality.process_profiles import HOSPITALITY_PROCESS_PROFILES
from verticals.hospitality.projections import HOSPITALITY_PROJECTIONS
from verticals.hospitality.worlds import HOSPITALITY_WORLDS


PACK_ROOT = Path(__file__).resolve().parent


def _load_durable_module():
    return import_module("verticals.hospitality.durable")


def build_pack() -> VerticalPack:
    domains = wire_domain_functions(
        dict(HOSPITALITY_DOMAINS),
        dict(HOSPITALITY_FUNCTIONS),
    )
    return VerticalPack(
        root=PACK_ROOT,
        name="hospitality",
        display_name="Hospitality",
        manifest_version="1",
        domains=domains,
        organisation_functions=HOSPITALITY_FUNCTIONS,
        agents=HOSPITALITY_AGENTS,
        authority=HOSPITALITY_AUTHORITY,
        personas=HOSPITALITY_PERSONAS,
        policy_sources=(PACK_ROOT / "policies" / "tools.yaml",),
        durable_functions=DurableFunctionRegistration(
            load_module=_load_durable_module,
            orchestrators=frozenset(
                profile.orchestrator
                for profile in HOSPITALITY_PROCESS_PROFILES.values()
            ),
            activities=frozenset(
                {
                    "hospitality_evidence_activity_trigger",
                    "hospitality_decision_activity_trigger",
                    "hospitality_command_activity_trigger",
                }
            ),
        ),
        personae_roots=(PACK_ROOT / "personae",),
        skill_roots=(PACK_ROOT / "skills",),
        mcp_modules=("verticals.hospitality.mcp_tools.operations",),
        external_capabilities=frozenset(),
        worlds=HOSPITALITY_WORLDS,
        default_world="hospitality",
        seed=SeedRegistration(bootstrap=bootstrap),
        projections=HOSPITALITY_PROJECTIONS,
        memory_workflow_types=tuple(domains),
        lifecycle=LifecycleRegistration(start=start),
        recordings=RecordingSources(curated_dirs=()),
        ui=load_ui_manifest(PACK_ROOT / "ui.json"),
        ramp_workflow_types=(),
    )
