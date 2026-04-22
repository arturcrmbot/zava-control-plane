# src/server/mcp_tools/__init__.py
from .query_fleet import make_query_fleet_tool
from .query_traces import make_query_traces_tool
from .compose_exception import make_compose_exception_tool
from .propose_skill_amp import make_propose_skill_amp_tool
from .dry_run_policy import make_dry_run_policy_tool, dry_run_policy_impl


def build_fleet_manager_tools(store, audit):
    return [
        make_query_fleet_tool(store),
        make_query_traces_tool(store),
        make_compose_exception_tool(store, audit),
        make_propose_skill_amp_tool(store),
        make_dry_run_policy_tool(store),
    ]
