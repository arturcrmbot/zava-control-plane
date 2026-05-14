"""Dedupe semantics for :class:`EntityReflector` (TASK-012).

Driving the same workflow event twice must produce:

* TWO ``entity.upserted`` bus events for each entity kind in the projection
  (entities are last-write-wins, no dedup at the entity level). The
  reflector also upserts a ``Workflow`` node per dispatch, so a Person
  projection produces 4 entity.upserted events across two replays
  (2 Workflow + 2 Person).
* ONE ``decision.recorded`` bus event (the natural-triple dedup at
  :meth:`EntityGraph.record_decision` rejects the second).
* ONE ``decision.recorded`` + ONE ``decision.deduped`` audit entry.
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api.server.services.entity_graph import (
    DecisionWrite,
    EntityGraph,
    EntityWrite,
)
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


def test_reflector_dedupes_decision_but_not_entity_on_replay(tmp_path: Path) -> None:
    event_bus = EventBus()
    store = StateStore()
    graph = EntityGraph(tmp_path / "g.kuzu")

    # The graph (not the reflector) emits entity.upserted, decision.recorded
    # and decision.deduped. Attach mocks here to capture those side effects.
    mock_bus = MagicMock()
    mock_audit = MagicMock()
    graph.attach(bus=mock_bus, audit=mock_audit)

    def fake_projection(_wf: Workflow):
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-T1",
                attrs={"name": "Alice"},
                source_workflows=("WF-DUP",),
            ),
            DecisionWrite(
                workflow_id="WF-DUP",
                phase="approve",
                persona_role="cfo",
                verdict="approved",
                reason="ok",
                decided_at="2026-05-09T10:00:00",
                source_event="workflow.completed",
                attributes={},
                decided_on=(),
            ),
        ]

    PROJECTIONS["test-dedupe-domain"] = fake_projection
    reflector = EntityReflector(event_bus, store, graph)
    reflector.start()
    try:
        store.upsert_workflow(_make_workflow("WF-DUP", "test-dedupe-domain"))

        event_bus.emit(FleetEvent(type="workflow.completed", workflow_id="WF-DUP"))
        event_bus.emit(FleetEvent(type="workflow.completed", workflow_id="WF-DUP"))

        emitted_types = [
            call.args[0].type for call in mock_bus.emit.call_args_list
        ]
        audit_actions = [call.args[0] for call in mock_audit.log.call_args_list]

        # 2 Person upserts + 2 Workflow upserts (the reflector materialises
        # the dispatching Workflow node before each projection's ops).
        assert emitted_types.count("entity.upserted") == 4, (
            f"expected 4 entity.upserted (2 Person + 2 Workflow, "
            f"last-write-wins), got {emitted_types!r}"
        )
        assert emitted_types.count("decision.recorded") == 1, (
            f"expected exactly 1 decision.recorded (dedup), got "
            f"{emitted_types!r}"
        )

        assert audit_actions.count("decision.recorded") == 1, (
            f"expected 1 decision.recorded audit entry, got {audit_actions!r}"
        )
        assert audit_actions.count("decision.deduped") == 1, (
            f"expected 1 decision.deduped audit entry, got {audit_actions!r}"
        )
    finally:
        reflector.aclose()
        del PROJECTIONS["test-dedupe-domain"]
