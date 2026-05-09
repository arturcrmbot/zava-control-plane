"""Comprehensive unknown-workflow_type guard for :class:`EntityReflector`
(TASK-014, locks CON-001).

A FleetEvent referencing a workflow whose ``type`` is not registered in
:data:`PROJECTIONS` must be a SILENT no-op:

* no audit emission of any kind from the reflector,
* no graph write,
* no exception.

Uses ``expense-claim`` (a real POC1 workflow type that has no projection
registered in sub-phase 2) so this test will keep biting if a future
change accidentally turns "unknown type" into an audited event.
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api.server.services.entity_graph import EntityGraph
from api.server.services.entity_projections import PROJECTIONS
from api.server.services.entity_reflector import EntityReflector
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.shared.events import FleetEvent
from api.shared.types import Workflow


def _make_workflow(workflow_id: str, workflow_type: str) -> Workflow:
    now = time.time()
    return Workflow(
        id=workflow_id,
        type=workflow_type,
        current_phase="Intake",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-Test",
    )


def test_reflector_silently_skips_poc1_expense_claim(tmp_path: Path) -> None:
    # Sanity: the POC1 type really is unregistered in sub-phase 2.
    assert "expense-claim" not in PROJECTIONS

    event_bus = EventBus()
    store = StateStore()
    graph = EntityGraph(tmp_path / "g.kuzu")

    # Mocks attached to BOTH the reflector and the graph so any audit /
    # bus emission anywhere in the dispatch path would show up.
    reflector_audit = MagicMock()
    graph_bus = MagicMock()
    graph_audit = MagicMock()
    graph.attach(bus=graph_bus, audit=graph_audit)

    store.upsert_workflow(_make_workflow("WF-POC1", "expense-claim"))

    reflector = EntityReflector(event_bus, store, graph, audit=reflector_audit)
    reflector.start()
    try:
        # Must not raise.
        event_bus.emit(
            FleetEvent(type="workflow.completed", workflow_id="WF-POC1")
        )

        # No audit emissions from the reflector itself (CON-001).
        assert reflector_audit.log.call_count == 0, (
            f"expected zero reflector audit entries, got "
            f"{reflector_audit.log.call_args_list!r}"
        )
        # Specifically: no entity.write.killed (governance was None, but
        # double-check we didn't somehow take the kill path).
        reflector_actions = [
            call.args[0] for call in reflector_audit.log.call_args_list
        ]
        assert "entity.write.killed" not in reflector_actions

        # No graph writes ⇒ the graph never emitted entity.upserted /
        # entity.linked / decision.recorded either.
        graph_emitted = [
            call.args[0].type for call in graph_bus.emit.call_args_list
        ]
        assert graph_emitted == [], (
            f"expected zero graph bus emissions, got {graph_emitted!r}"
        )
        graph_audit_actions = [
            call.args[0] for call in graph_audit.log.call_args_list
        ]
        assert graph_audit_actions == [], (
            f"expected zero graph audit entries, got {graph_audit_actions!r}"
        )

        # And nothing materialised.
        assert graph.get("PERSON-WF-POC1") is None
        assert graph.get("WF-POC1") is None
    finally:
        reflector.aclose()
