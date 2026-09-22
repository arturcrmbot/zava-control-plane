"""Zava Bank vertical pack manifest.

Auto-discovered by the vertical loader: any ``verticals/<name>/manifest.py``
exporting ``build_pack()`` is registered without touching a global registry.
"""
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
from verticals.banking.agents import BANKING_AGENTS
from verticals.banking.authority import BANKING_AUTHORITY
from verticals.banking.detail import workflow_detail
from verticals.banking.domains import BANKING_DOMAINS
from verticals.banking.functions import BANKING_FUNCTIONS
from verticals.banking.lifecycle import bootstrap, start
from verticals.banking.personas import BANKING_PERSONAS
from verticals.banking.projections import BANKING_PROJECTIONS
from verticals.banking.worlds.registration import BANKING_WORLDS

PACK_ROOT = Path(__file__).resolve().parent


def _load_durable_module():
    return import_module("verticals.banking.durable")


def build_pack() -> VerticalPack:
    domains = wire_domain_functions(dict(BANKING_DOMAINS), dict(BANKING_FUNCTIONS))
    live_domains = [domain for domain in domains.values() if not domain.stub]
    return VerticalPack(
        root=PACK_ROOT,
        name="banking",
        display_name="Zava Bank",
        manifest_version="1",
        domains=domains,
        organisation_functions=BANKING_FUNCTIONS,
        agents=BANKING_AGENTS,
        authority=BANKING_AUTHORITY,
        personas=BANKING_PERSONAS,
        policy_sources=(PACK_ROOT / "policies" / "tools.yaml",),
        durable_functions=DurableFunctionRegistration(
            load_module=_load_durable_module,
            orchestrators=frozenset(
                domain.orchestrator_name for domain in live_domains
            ),
            activities=frozenset(
                {
                    "fraud_evidence_activity_trigger",
                    "fraud_trace_activity_trigger",
                    "fraud_agent_activity_trigger",
                    "fraud_governance_activity_trigger",
                    "fraud_command_activity_trigger",
                    "case_evidence_activity_trigger",
                    "case_agent_activity_trigger",
                    "case_governance_activity_trigger",
                    "case_command_activity_trigger",
                }
            ),
        ),
        personae_roots=(PACK_ROOT / "personae",),
        skill_roots=(PACK_ROOT / "skills",),
        mcp_modules=(
            "verticals.banking.mcp_tools.fraud",
            "verticals.banking.mcp_tools.supporting",
        ),
        external_capabilities=frozenset(),
        worlds=dict(BANKING_WORLDS),
        default_world="banking",
        seed=SeedRegistration(bootstrap=bootstrap),
        projections=dict(BANKING_PROJECTIONS),
        memory_workflow_types=tuple(
            domain.workflow_type for domain in live_domains
        ),
        lifecycle=LifecycleRegistration(start=start),
        recordings=RecordingSources(curated_dirs=(PACK_ROOT / "recordings",)),
        ui=load_ui_manifest(PACK_ROOT / "ui.json"),
        # The autonomy switch: every non-stub domain that owns a spawner is
        # driven continuously by the ramp loop. The hero is world-owned and
        # deliberately absent here -- its objective comes from a sensor.
        ramp_workflow_types=tuple(
            domain.workflow_type for domain in live_domains if domain.spawn_fn
        ),
        workflow_detail_hook=workflow_detail,
    )
