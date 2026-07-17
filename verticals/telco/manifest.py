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
from verticals.telco.agents import TELCO_AGENTS
from verticals.telco.authority import TELCO_AUTHORITY
from verticals.telco.domains import TELCO_DOMAINS
from verticals.telco.functions import TELCO_FUNCTIONS
from verticals.telco.lifecycle import bootstrap, start
from verticals.telco.personas import TELCO_PERSONAS
from verticals.telco.projections import TELCO_PROJECTIONS
from verticals.telco.worlds import TELCO_WORLDS


PACK_ROOT = Path(__file__).resolve().parent


def _load_durable_module():
    return import_module("verticals.telco.durable")


def build_pack() -> VerticalPack:
    domains = wire_domain_functions(
        dict(TELCO_DOMAINS),
        dict(TELCO_FUNCTIONS),
    )
    return VerticalPack(
        root=PACK_ROOT,
        name="telco",
        display_name="Telco",
        manifest_version="1",
        domains=domains,
        organisation_functions=TELCO_FUNCTIONS,
        agents=TELCO_AGENTS,
        authority=TELCO_AUTHORITY,
        personas=TELCO_PERSONAS,
        policy_sources=(PACK_ROOT / "policies" / "tools.yaml",),
        durable_functions=DurableFunctionRegistration(
            load_module=_load_durable_module,
            orchestrators=frozenset(
                domain.orchestrator_name for domain in domains.values()
            ),
            activities=frozenset(
                {
                    "network_incident_impact_activity_trigger",
                    "network_incident_reroute_activity_trigger",
                    "customer_care_impact_activity_trigger",
                    "customer_care_entitlement_activity_trigger",
                    "customer_care_execution_activity_trigger",
                    "order_activation_feasibility_activity_trigger",
                    "order_activation_prepare_activity_trigger",
                    "telco_cascade_decision_activity_trigger",
                }
            ),
        ),
        personae_roots=(PACK_ROOT / "personae",),
        skill_roots=(PACK_ROOT / "skills",),
        mcp_modules=(
            "verticals.telco.mcp_tools.customer_care",
            "verticals.telco.mcp_tools.network",
            "verticals.telco.mcp_tools.operations",
            "verticals.telco.mcp_tools.commercial",
            "verticals.telco.mcp_tools.twin",
        ),
        external_capabilities=frozenset(),
        worlds=TELCO_WORLDS,
        default_world="telco",
        seed=SeedRegistration(bootstrap=bootstrap),
        projections=TELCO_PROJECTIONS,
        memory_workflow_types=tuple(domains),
        lifecycle=LifecycleRegistration(start=start),
        recordings=RecordingSources(
            curated_dirs=(PACK_ROOT / "recordings",)
        ),
        ui=load_ui_manifest(PACK_ROOT / "ui.json"),
        ramp_workflow_types=(),
    )
