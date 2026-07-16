from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from verticals.telco.mcp_tools.customer_care import lookup_entitlement
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_bridge import WorldBridge
from api.server.world.service import ActorWorldService


async def test_customer_impact_creates_and_resolves_canonical_care_workflow(
    monkeypatch,
):
    world = ActorWorldService.telco(seed=42, bus=EventBus(), minutes_per_second=1000)
    state = SimpleNamespace(
        bus=world.bus,
        world_service=world,
        world_last_response=None,
        store=StateStore(),
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
        runtime=world.vertical_runtime,
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    world.inject_site_failure("SITE-01")
    world.runtime.run_until(2)
    sensor = next(
        event
        for event in world.runtime.journal
        if event.type == "sensor.tripped"
        and event.actor_id == "sensor:customer_impact"
    )
    account_id = sensor.payload["account_ids"][0]
    account = world.scenario.accounts[account_id]
    entitlement = lookup_entitlement(
        account.segment,
        account.vulnerable,
        account.approval_required,
    )
    workflow_id = f"care-{sensor.event_id}"

    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(
            return_value={
                "id": "care-instance-1",
                "statusQueryGetUri": "status://care",
            }
        ),
    )
    bridge = WorldBridge(state)
    bridge._await_output = AsyncMock(
        return_value={
            "command": {
                "command_id": f"care-{sensor.event_id}",
                "trace_id": sensor.trace_id,
                "issued_by": "customer_care",
                "type": "apply_customer_remediation",
                "payload": {
                    "approval_decision": (
                        "approve" if entitlement["requires_approval"] else "policy"
                    ),
                    "actions": [
                        {
                            "account_id": account_id,
                            "channel": "sms",
                            "message": "We restored your service.",
                            "credit_amount": entitlement["credit_amount"],
                            "authority_approved": True,
                        }
                    ]
                },
            },
            "reasoning": "policy-grounded care action",
        }
    )

    await bridge._drive(sensor.to_dict())

    workflow = state.store.get_workflow(workflow_id)
    assert workflow.status == "completed"
    assert workflow.current_phase == "Outcome Verification"
    assert workflow.payload["outcome"]["status"] == "resolved"
    assert workflow.payload["customer_impact"]["impacted_accounts"]
    objective = world.objectives.get(f"obj-{sensor.event_id}")
    assert objective.status == "resolved"
    assert (
        world.scenario.accounts[account_id].total_credits
        == entitlement["credit_amount"]
    )
    assert any(
        event.type == "care.completed" and event.trace_id == sensor.trace_id
        for event in world.runtime.journal
    )
