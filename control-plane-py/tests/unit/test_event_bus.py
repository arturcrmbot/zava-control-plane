import pytest
from src.server.services.event_bus import EventBus
from src.shared.events import FleetEvent


@pytest.mark.asyncio
async def test_delivers_to_subscriber():
    bus = EventBus()
    received = []
    bus.on("workflow.started", lambda e: received.append(e))
    bus.emit(FleetEvent(type="workflow.started", workflow_id="A"))
    assert len(received) == 1
    assert received[0].workflow_id == "A"


@pytest.mark.asyncio
async def test_on_any_receives_all():
    bus = EventBus()
    received = []
    bus.on_any(lambda e: received.append(e))
    bus.emit(FleetEvent(type="fleet.tick"))
    assert len(received) == 1


@pytest.mark.asyncio
async def test_unsubscribe_works():
    bus = EventBus()
    received = []
    handler = lambda e: received.append(e)
    off = bus.on("workflow.started", handler)
    off()
    bus.emit(FleetEvent(type="workflow.started", workflow_id="A"))
    assert len(received) == 0
