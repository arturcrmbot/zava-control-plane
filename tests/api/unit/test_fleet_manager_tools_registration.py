"""build_fleet_manager_tools registration — locks the FM session toolset.

These tools form the Fleet Manager's surface. The behaviour-change loop
(AC #7) needs `query_reviewer_decisions`; the cost-per-task report (AC #13)
needs `query_economics`. This test makes accidental removal during
refactors loud."""
from __future__ import annotations

from api.server.mcp_tools import build_fleet_manager_tools
from api.server.services.audit_logger import AuditLogger
from api.server.services.state_store import StateStore


def test_fleet_manager_tools_include_behaviour_change_surface():
    tools = build_fleet_manager_tools(StateStore(), AuditLogger())
    names = {t.name for t in tools}
    # Existing core surface.
    assert {"query_fleet", "query_traces", "compose_exception",
            "propose_skill_amplification", "dry_run_policy"} <= names
    # AC #7 — behaviour-change loop needs the reviewer-decisions surface.
    assert "query_reviewer_decisions" in names
    # AC #13 — cost-per-task report needs the economics surface.
    assert "query_economics" in names


def test_each_fleet_manager_tool_has_handler_and_description():
    tools = build_fleet_manager_tools(StateStore(), AuditLogger())
    for t in tools:
        assert t.name, f"tool with empty name: {t!r}"
        assert t.handler is not None, f"tool {t.name!r} has no handler"
        assert t.description, f"tool {t.name!r} has empty description"
