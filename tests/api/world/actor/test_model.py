from dataclasses import FrozenInstanceError

import pytest

from api.server.world.model import SimulationCommand, SimulationEvent


def test_event_serialises_all_causal_fields():
    event = SimulationEvent(
        seq=7,
        event_id="evt-00000007",
        sim_time=12.5,
        type="ticket.queued",
        actor_id="TKT-1",
        target_id="queue:support",
        cause_event_id="evt-00000006",
        trace_id="ticket-TKT-1",
        payload={"severity": "high"},
    )
    assert event.to_dict() == {
        "seq": 7,
        "event_id": "evt-00000007",
        "sim_time": 12.5,
        "type": "ticket.queued",
        "actor_id": "TKT-1",
        "target_id": "queue:support",
        "cause_event_id": "evt-00000006",
        "trace_id": "ticket-TKT-1",
        "payload": {"severity": "high"},
    }


def test_event_and_command_are_frozen():
    event = SimulationEvent(
        seq=1, event_id="evt-00000001", sim_time=0.0, type="simulation.started",
        actor_id=None, target_id=None, cause_event_id=None,
        trace_id="evt-00000001", payload={},
    )
    command = SimulationCommand(
        command_id="cmd-1", trace_id="trace-1", issued_by="staffing",
        type="reallocate_workers", payload={"worker_ids": ["WRK-1"]},
    )
    with pytest.raises(FrozenInstanceError):
        event.type = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.type = "changed"  # type: ignore[misc]


def test_command_serialises_to_wire_shape():
    command = SimulationCommand(
        command_id="cmd-1",
        trace_id="trace-1",
        issued_by="surge_staffing",
        type="reallocate_workers",
        payload={"worker_ids": ["WRK-1"], "duration_minutes": 30},
    )
    assert command.to_dict()["type"] == "reallocate_workers"
    assert command.to_dict()["payload"]["duration_minutes"] == 30
