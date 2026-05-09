# src/server/mcp_tools/__init__.py
from .query_fleet import make_query_fleet_tool
from .query_traces import make_query_traces_tool
from .compose_exception import make_compose_exception_tool
from .propose_skill_amp import make_propose_skill_amp_tool
from .dry_run_policy import make_dry_run_policy_tool, dry_run_policy_impl
from .query_reviewer_decisions import query_reviewer_decisions_tool
from .query_economics import query_economics_tool
from . import claim_lookup  # noqa: F401  (Phase 1 Intake — Workday/Concur dispatcher)
from . import avatar_render  # noqa: F401  (Phase 10 Onboarding — Azure Speech avatar)
from . import image_gen  # noqa: F401  (POC3 — Foundry gpt-image-2 for creative-campaign)

# Phase 3 — Function Fleet Manager surface (TASK-019..-024).
from .query_fleet_state import make_query_fleet_state_tool
from .query_kpi import make_query_kpi_tool
from .query_recent_decisions import make_query_recent_decisions_tool
from .query_entity import make_query_entity_tool
from .find_entities import make_find_entities_tool


def build_fleet_manager_tools(store, audit):
    return [
        make_query_fleet_tool(store),
        make_query_traces_tool(store),
        make_compose_exception_tool(store, audit),
        make_propose_skill_amp_tool(store),
        make_dry_run_policy_tool(store),
        # Behaviour-change loop: surface SSC reviewer decision clusters
        # so the FM can propose autonomy on stable patterns.
        query_reviewer_decisions_tool,
        # Cost-per-task report: weekly cost aggregate by verdict.
        query_economics_tool,
    ]


def build_function_fm_tools(store, audit, graph, function_name: str):
    """Build the five in-process MCP tools scoped to a single function.

    Returns the list of tools a per-function FleetManagerService session
    is wired with at construction. The tools are independent instances —
    constructing them for ``finance`` and ``hr`` produces two distinct
    sets, each carrying its own bound ``function_name`` closure.

    Plan: plan/feature-agentic-org-phase-3-function-fms.md TASK-024.
    """
    return [
        make_query_fleet_state_tool(store, function_name=function_name),
        make_query_kpi_tool(kpi_store=None, function_name=function_name),
        make_query_recent_decisions_tool(graph, function_name=function_name),
        make_query_entity_tool(graph),
        make_find_entities_tool(graph, audit),
    ]
