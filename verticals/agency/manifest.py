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
from verticals.agency.agents import AGENCY_AGENTS
from verticals.agency.authority import AGENCY_AUTHORITY
from verticals.agency.domains import AGENCY_DOMAINS
from verticals.agency.functions import AGENCY_FUNCTIONS
from verticals.agency.lifecycle import bootstrap, start
from verticals.agency.projections import AGENCY_PROJECTIONS
from verticals.agency.worlds import AGENCY_WORLDS


PACK_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACK_ROOT.parents[1]

AGENCY_EXTERNAL_CAPABILITIES = frozenset(
    {
        "acs_dial",
        "betrvg_check",
        "comp_band_lookup",
        "d365.parseInvoice",
        "eeo_check",
        "finance_bp_card_compose",
        "graph_calendar",
        "graph_invite",
        "graph_mail",
        "greenhouse_post",
        "jd_library_search",
        "linkedin_profile_fetch",
        "linkedin_search",
        "offer_template_fetch",
        "payment.reconcileStatement",
        "propose_skill_amplification",
        "scoring_rubric_load",
        "servicenow_jml",
        "transcript_score",
        "workday.getExpenseClaim",
        "workday.getVendor",
        "workday_position",
    }
)


def _load_durable_module():
    return import_module("verticals.agency.durable")


def _mcp_modules() -> tuple[str, ...]:
    root = REPO_ROOT / "api" / "server" / "mcp_tools"
    return tuple(
        f"api.server.mcp_tools.{path.stem}"
        for path in sorted(root.glob("*.py"))
        if not path.stem.startswith("_") and path.stem != "__init__"
    )


def build_pack() -> VerticalPack:
    domains = wire_domain_functions(
        dict(AGENCY_DOMAINS),
        dict(AGENCY_FUNCTIONS),
    )
    orchestrators = {
        domain.orchestrator_name
        for domain in domains.values()
        if not domain.stub
    }
    orchestrators.add("SurgeStaffingOrchestrator")
    return VerticalPack(
        root=PACK_ROOT,
        name="agency",
        display_name="Agency",
        manifest_version="1",
        domains=domains,
        organisation_functions=AGENCY_FUNCTIONS,
        agents=AGENCY_AGENTS,
        authority=AGENCY_AUTHORITY,
        policy_sources=(REPO_ROOT / "data" / "policies" / "tools.yaml",),
        durable_functions=DurableFunctionRegistration(
            load_module=_load_durable_module,
            orchestrators=frozenset(orchestrators),
            activities=frozenset(),
        ),
        personae_roots=(REPO_ROOT / "api" / "server" / "personae",),
        skill_roots=(REPO_ROOT / "api" / "server" / "skills",),
        mcp_modules=_mcp_modules(),
        external_capabilities=AGENCY_EXTERNAL_CAPABILITIES,
        worlds=AGENCY_WORLDS,
        default_world=None,
        seed=SeedRegistration(bootstrap=bootstrap),
        projections=AGENCY_PROJECTIONS,
        memory_workflow_types=("hiring",),
        lifecycle=LifecycleRegistration(start=start),
        recordings=RecordingSources(
            curated_dirs=(PACK_ROOT / "recordings",)
        ),
        ui=load_ui_manifest(PACK_ROOT / "ui.json"),
        ramp_workflow_types=tuple(
            domain.workflow_type
            for domain in domains.values()
            if not domain.stub and domain.spawn_fn
        ),
    )
