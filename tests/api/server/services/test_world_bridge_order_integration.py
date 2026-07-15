from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_bridge import WorldBridge
from api.server.world.service import ActorWorldService


async def test_service_order_reaches_canonical_workflow_and_world_activation(
    monkeypatch,
):
    world = ActorWorldService.telco(
        seed=42, bus=EventBus(), minutes_per_second=1000
    )
    state = SimpleNamespace(
        bus=world.bus,
        world_service=world,
        world_last_response=None,
        store=StateStore(),
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
        domain_memories={},
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    order_id = world.submit_service_order(
        account_id="ACC-00001",
        product="fiber-1gb",
        requested_site_id="SITE-02",
    )
    sensor = world.runtime.journal[-1]
    workflow_id = f"order-{sensor.event_id}"
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(
            return_value={
                "id": "order-instance-1",
                "statusQueryGetUri": "status://order",
            }
        ),
    )
    bridge = WorldBridge(state)
    bridge._await_output = AsyncMock(
        return_value={
            "command": {
                "command_id": f"activate-{order_id}",
                "trace_id": sensor.trace_id,
                "issued_by": "service_fulfillment",
                "type": "activate_service_order",
                "payload": {
                    "order_id": order_id,
                    "capacity_approved": False,
                },
            },
            "reasoning": "capacity available",
        }
    )

    await bridge._drive(sensor.to_dict())

    workflow = state.store.get_workflow(workflow_id)
    assert workflow.status == "completed"
    assert workflow.current_phase == "Activation Verification"
    assert world.scenario.orders[order_id].status == "activated"
    assert world.objectives.get(f"obj-{sensor.event_id}").status == "resolved"
