from __future__ import annotations

import pytest

from api.server.state import AppState
from api.shared.events import FleetEvent
from api.shared.types import Workflow
from api.shared.vertical_loader import build_runtime


@pytest.mark.parametrize("mode", ["live", "replay", " RePlAy "])
async def test_only_live_events_trigger_graph_projection(tmp_path, monkeypatch, mode):
    monkeypatch.setenv("ZAVA_MODE", mode)
    monkeypatch.setenv("ENTITY_PLANE_ENABLED", "1")
    monkeypatch.setenv("MEMORY_BACKEND", "fallback")
    runtime = build_runtime({"ZAVA_VERTICAL": "agency"}, data_root=tmp_path)
    state = AppState(runtime=runtime)
    try:
        workflow = Workflow(
            id="VKY-REPLAY-ISOLATION",
            type="vendor-kyc",
            current_phase="Intake",
            created_at=1_716_399_200.0,
            sla_due_at=1_716_485_600.0,
            jurisdiction="London-Zava",
            agency="TestAgency",
            payload={
                "vendor_name": "Replay Isolation Vendor",
                "country_of_incorporation": "GB",
                "proposing_agency": "TestAgency",
                "scenario": "clean",
            },
        )
        state.store.upsert_workflow(workflow)
        before_audit = state.audit.list()
        before_decisions = len(state.governance._decisions)
        delivered = []
        state.bus.on("workflow.completed", delivered.append)
        event = FleetEvent(type="workflow.completed", workflow_id=workflow.id)
        for _ in range(5):
            state.bus.emit(event)
        state.bus.emit(FleetEvent(
            type="workflow.sub_spawned",
            parent_workflow_id=workflow.id,
            child_workflow_id="CHILD-REPLAY-ISOLATION",
            child_workflow_type="vendor-kyc",
        ))

        assert delivered == [event] * 5
        vendor = state.entities.get("ORG-vendor-replay-isolation-vendor")
        child = state.entities.get("CHILD-REPLAY-ISOLATION")
        if mode == "live":
            assert vendor is not None
            assert child is not None
            assert len(state.audit.list()) > len(before_audit)
            assert state.entity_reflector._off is not None
            assert state.meta_workflow_reflector._started is True
        else:
            assert vendor is None
            assert child is None
            assert state.audit.list() == before_audit
            assert len(state.governance._decisions) == before_decisions
            assert state.entity_reflector._off is None
            assert state.meta_workflow_reflector._started is False
    finally:
        await state.aclose()
