"""Route contract for Travel's actor-world-disabled Durable diagnostic."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import api.server.routes.world as world_routes
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.shared.vertical_loader import build_runtime


def _disabled_travel_state() -> SimpleNamespace:
    state = SimpleNamespace(
        runtime=build_runtime({"ZAVA_VERTICAL": "travel"}),
        bus=EventBus(),
        store=StateStore(),
        hub=SimpleNamespace(broadcast=lambda *_args, **_kwargs: None),
        audit=SimpleNamespace(),
        orchestration_history={},
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    return state


@pytest.mark.asyncio
async def test_disabled_actor_world_diagnostic_route_builds_real_input_and_starts_durable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _disabled_travel_state()
    captured: dict[str, object] = {}

    class FakeDiagnosticBridge:
        def __init__(self, received_state: SimpleNamespace) -> None:
            assert received_state is state

        async def start_diagnostic(self, *, sensor_event, responder, observation) -> str:
            captured.update(
                sensor_event=sensor_event,
                responder=responder,
                observation=observation,
            )
            return "fdr-diagnostic-evt-00000157"

    monkeypatch.setattr(world_routes, "app_state", state)
    monkeypatch.setattr(world_routes, "WorldBridge", FakeDiagnosticBridge)

    response = await world_routes.run_actor_world_diagnostic(
        "flight-disruption-recovery",
        world_routes.DirectDiagnosticRequest(mode="direct-diagnostic"),
    )

    assert response == {
        "workflow_id": "fdr-diagnostic-evt-00000157",
        "mode": "direct-diagnostic",
        "source_sensor_event_id": "evt-00000157",
    }
    assert captured["responder"].workflow_type == "flight-disruption-recovery"
    assert captured["sensor_event"]["payload"]["diagnostic"] is True
    assert captured["observation"]["booking_id"] == "BKG-4"
