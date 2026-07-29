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
from verticals.airline.agents import AIRLINE_AGENTS
from verticals.airline.authority import AIRLINE_AUTHORITY
from verticals.airline.detail import workflow_detail
from verticals.airline.domains import AIRLINE_DOMAINS
from verticals.airline.functions import AIRLINE_FUNCTIONS
from verticals.airline.lifecycle import bootstrap, start
from verticals.airline.personas import AIRLINE_PERSONAS
from verticals.airline.process_profiles import (
    AIRLINE_PROCESS_PROFILES,
    WORKFLOW_TYPE,
)
from verticals.airline.projections import AIRLINE_PROJECTIONS
from verticals.airline.worlds.registration import AIRLINE_WORLDS


PACK_ROOT = Path(__file__).resolve().parent


def _load_durable_module():
    return import_module("verticals.airline.durable")


def build_pack() -> VerticalPack:
    domains = wire_domain_functions(
        dict(AIRLINE_DOMAINS),
        dict(AIRLINE_FUNCTIONS),
    )
    return VerticalPack(
        root=PACK_ROOT,
        name="airline",
        display_name="Synthetic Airline Operations",
        manifest_version="1",
        domains=domains,
        organisation_functions=AIRLINE_FUNCTIONS,
        agents=AIRLINE_AGENTS,
        authority=AIRLINE_AUTHORITY,
        personas=AIRLINE_PERSONAS,
        policy_sources=(PACK_ROOT / "policies" / "tools.yaml",),
        durable_functions=DurableFunctionRegistration(
            load_module=_load_durable_module,
            orchestrators=frozenset(profile.orchestrator for profile in AIRLINE_PROCESS_PROFILES.values()),
            activities=frozenset(
                {
                    "airline_evidence_activity_trigger",
                    "airline_agent_activity_trigger",
                    "airline_admission_activity_trigger",
                    "airline_governance_activity_trigger",
                    "airline_command_activity_trigger",
                }
            ),
        ),
        personae_roots=(PACK_ROOT / "personae",),
        skill_roots=(PACK_ROOT / "skills",),
        mcp_modules=("verticals.airline.mcp_tools.operations",),
        external_capabilities=frozenset(),
        worlds=dict(AIRLINE_WORLDS),
        default_world="airline",
        seed=SeedRegistration(bootstrap=bootstrap),
        projections=dict(AIRLINE_PROJECTIONS),
        memory_workflow_types=(WORKFLOW_TYPE,),
        lifecycle=LifecycleRegistration(start=start),
        recordings=RecordingSources(curated_dirs=()),
        ui=load_ui_manifest(PACK_ROOT / "ui.json"),
        ramp_workflow_types=(),
        workflow_detail_hook=workflow_detail,
    )
