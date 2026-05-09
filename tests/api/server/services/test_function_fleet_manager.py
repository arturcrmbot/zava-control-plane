"""Tests for FunctionFleetManager (Phase 3 TASK-029)."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.mcp_tools import build_function_fm_tools
from api.server.services.audit_logger import AuditLogger
from api.server.services.entity_graph import EntityGraph
from api.server.services.event_bus import EventBus
from api.server.services.fleet_manager_service import (
    FleetManagerService,
    FunctionFleetManager,
    _function_identity_section,
)
from api.server.services.sse_hub import SSEHub
from api.server.services.state_store import StateStore


@pytest.fixture()
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    yield g
    g.close()


def test_function_alias_is_same_class():
    assert FunctionFleetManager is FleetManagerService


def test_construction_with_function_finance(graph):
    bus = EventBus()
    store = StateStore()
    audit = AuditLogger()
    tools = build_function_fm_tools(store, audit, graph, "finance")
    fm = FunctionFleetManager(
        bus=bus, store=store, audit=audit,
        function="finance", tools=tools,
    )
    assert fm._function == "finance"
    assert fm._tools_override is tools


def test_skill_text_contains_function_identity_section(graph):
    bus = EventBus()
    store = StateStore()
    audit = AuditLogger()
    tools = build_function_fm_tools(store, audit, graph, "finance")
    fm = FunctionFleetManager(
        bus=bus, store=store, audit=audit,
        function="finance", tools=tools,
    )
    skill = fm._build_skill_text()
    assert "## You are the Finance Function FM" in skill
    assert "## KPIs you own" in skill
    assert "dso" in skill
    assert "## Domains you cover" in skill
    assert "ap-invoice" in skill
    assert "## Persona hierarchy" in skill
    assert "cfo" in skill
    assert "## Ambient watchers active for you" in skill


def test_function_none_skill_matches_fleet_wide(graph):
    bus = EventBus()
    store = StateStore()
    audit = AuditLogger()
    fleet = FleetManagerService(bus=bus, store=store, audit=audit)
    skill = fleet._build_skill_text()
    # No function identity header — that block is only prepended when
    # ``function=`` is set.
    assert "## You are the" not in skill
    assert "Domains under supervision" in skill  # legacy domain catalogue


def test_per_function_sse_topic_registered():
    hub = SSEHub()
    hub.register("fleet-manager.finance")
    # subscribe must succeed for a registered dynamic topic.
    q = hub.subscribe("fleet-manager.finance")
    assert q is not None


def test_identity_section_unknown_function_raises():
    with pytest.raises(ValueError, match="unknown function"):
        _function_identity_section("not-a-function")
