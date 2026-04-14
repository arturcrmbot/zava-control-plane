import asyncio
import pytest
from src.server.services.fleet_manager_queue import FleetManagerQueue, QueueEntry


@pytest.mark.asyncio
async def test_debounces_per_workflow():
    calls = []

    async def proc(batch):
        calls.append(list(batch))

    q = FleetManagerQueue(proc, debounce_ms=100)
    q.enqueue(QueueEntry(workflow_id="A", reason="x"))
    q.enqueue(QueueEntry(workflow_id="A", reason="y"))
    q.enqueue(QueueEntry(workflow_id="A", reason="z"))
    await asyncio.sleep(0.2)
    assert len(calls) == 1
    assert len(calls[0]) == 1


@pytest.mark.asyncio
async def test_batches_multiple_workflows():
    calls = []

    async def proc(batch):
        calls.append(list(batch))

    q = FleetManagerQueue(proc, debounce_ms=100)
    q.enqueue(QueueEntry(workflow_id="A", reason="x"))
    q.enqueue(QueueEntry(workflow_id="B", reason="x"))
    q.enqueue(QueueEntry(workflow_id="C", reason="x"))
    await asyncio.sleep(0.2)
    assert len(calls) == 1
    assert sorted(e.workflow_id for e in calls[0]) == ["A", "B", "C"]
