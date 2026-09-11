from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor


@pytest.mark.asyncio
async def test_started_callback_initialises_missing_workflow_and_output():
    state = SimpleNamespace(
        store=StateStore(),
        bus=EventBus(),
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
    )
    ingestor = WorkflowEventIngestor(state)

    await ingestor.ingest(
        "AUR-CALLBACK-1",
        "aurora-callback-instance",
        "workflow.started",
        {
            "workflow_type": "aurora-budget-response",
            "workflow": {
                "current_phase": "Observe budget signal",
                "jurisdiction": "London-Zava",
                "agency": "Zava",
                "payload": {
                    "request_id": "callback-request",
                    "brand_id": "BRAND-aurora",
                    "count": 2,
                },
            },
        },
        at=100.0,
    )
    workflow = state.store.get_workflow("AUR-CALLBACK-1")
    assert workflow is not None
    assert workflow.orchestration_instance_id == "aurora-callback-instance"
    assert workflow.payload["request_id"] == "callback-request"

    await ingestor.ingest(
        "AUR-CALLBACK-1",
        "aurora-callback-instance",
        "workflow.output",
        {"slot": "recommendation", "data": {"recommendation": "freeze"}},
        at=101.0,
    )
    assert state.store.get_workflow("AUR-CALLBACK-1").payload["outputs"] == {
        "recommendation": {"recommendation": "freeze"}
    }


@pytest.mark.asyncio
async def test_started_callback_initialises_ap_child_with_parent_identity():
    state = SimpleNamespace(
        store=StateStore(),
        bus=EventBus(),
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
    )
    ingestor = WorkflowEventIngestor(state)

    await ingestor.ingest(
        "API-AUR-001",
        "aurora-child-instance-001",
        "workflow.started",
        {
            "workflow_type": "ap-invoice",
            "workflow": {
                "current_phase": "Invoice Lookup",
                "jurisdiction": "London-Zava",
                "agency": "Zava",
                "payload": {
                    "parent_workflow_id": "AUR-CALLBACK-1",
                    "invoice": {
                        "invoice_id": "INV-AUR-001",
                        "brand_id": "BRAND-aurora",
                    },
                    "scenario": "matched-clean",
                },
            },
        },
        at=200.0,
    )

    child = state.store.get_workflow("API-AUR-001")
    assert child is not None
    assert child.type == "ap-invoice"
    assert child.payload["parent_workflow_id"] == "AUR-CALLBACK-1"
    assert child.payload["invoice"]["brand_id"] == "BRAND-aurora"
