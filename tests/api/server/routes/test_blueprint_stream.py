from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from api.server.routes import blueprint
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent


class _DisconnectedRequest:
    async def is_disconnected(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_live_bus_overflow_drops_events_without_loop_errors(monkeypatch):
    bus = EventBus()
    monkeypatch.setattr(blueprint.app_state, "bus", bus)
    monkeypatch.setattr(
        blueprint,
        "_OBSERVATORY_CAP",
        SimpleNamespace(allow=lambda: True),
    )
    monkeypatch.setattr(
        blueprint,
        "_normalise_event",
        lambda event: {"type": event.type},
    )
    monkeypatch.setattr(blueprint, "load_recorded_templates", lambda runtime: [])
    monkeypatch.setattr(blueprint, "_STREAM_TEMPLATES", [])

    loop = asyncio.get_running_loop()
    errors: list[dict] = []
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: errors.append(context))

    response = await blueprint.blueprint_stream(_DisconnectedRequest())
    try:
        for index in range(401):
            bus.emit(FleetEvent(type=f"test.event.{index}"))
        await asyncio.sleep(0)

        queue_errors = [
            context
            for context in errors
            if isinstance(context.get("exception"), asyncio.QueueFull)
        ]
        assert queue_errors == []
    finally:
        async for _ in response.body_iterator:
            pass
        loop.set_exception_handler(previous_handler)
