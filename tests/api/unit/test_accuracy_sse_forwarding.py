"""accuracy.* events emitted on the bus surface on the `fleet` SSE topic."""
from __future__ import annotations
import asyncio
import json

import pytest

# Side-effect import: brings the FastAPI app + routes into scope. The
# bus.on_any -> hub.broadcast wiring used to live at module-import time
# but was hoisted into the FastAPI lifespan so each app instance owns
# exactly one subscription. The autouse fixture below replays that
# wiring per test.
import api.server.main  # noqa: F401  (side-effect import)
from api.server.state import app_state
from api.shared.events import FleetEvent


@pytest.fixture(autouse=True)
def _wire_bus_to_hub():
    off = app_state.bus.on_any(
        lambda e: app_state.hub.broadcast("fleet", e.model_dump())
    )
    try:
        yield
    finally:
        try:
            off()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_accuracy_progress_event_broadcast_to_fleet_topic():
    q = app_state.hub.subscribe("fleet")
    try:
        ev = FleetEvent(
            type="accuracy.progress",
            workflow_id="acc-test",
            run_id="acc-test",
            index=1,
            total=3,
            claim_id="CLM-0000",
            correct=True,
        )
        app_state.bus.emit(ev)

        # The bus.on_any handler broadcasts synchronously; the queued payload should be there.
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        data = json.loads(msg)
        assert data["type"] == "accuracy.progress"
        assert data["run_id"] == "acc-test"
        assert data["claim_id"] == "CLM-0000"
        assert data["correct"] is True
    finally:
        app_state.hub.unsubscribe("fleet", q)


@pytest.mark.asyncio
async def test_accuracy_complete_event_broadcast_to_fleet_topic():
    q = app_state.hub.subscribe("fleet")
    try:
        ev = FleetEvent(
            type="accuracy.complete",
            workflow_id="acc-test-2",
            run_id="acc-test-2",
            summary={"overall_accuracy": 0.974, "n": 300},
        )
        app_state.bus.emit(ev)

        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        data = json.loads(msg)
        assert data["type"] == "accuracy.complete"
        assert data["summary"]["overall_accuracy"] == 0.974
    finally:
        app_state.hub.unsubscribe("fleet", q)
