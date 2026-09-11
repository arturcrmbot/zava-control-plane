import asyncio
import pytest
from api.server.services.fleet_manager_queue import FleetManagerQueue, QueueEntry


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


@pytest.mark.asyncio
async def test_work_arriving_during_batch_drains_without_another_wake():
    started = asyncio.Event()
    release = asyncio.Event()
    batches = []
    active = 0
    max_active = 0

    async def process(batch):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        batches.append([(entry.workflow_id, entry.reason) for entry in batch])
        if len(batches) == 1:
            started.set()
            await release.wait()
        active -= 1

    queue = FleetManagerQueue(process, debounce_ms=0)
    queue.enqueue(QueueEntry(workflow_id="A", reason="first"))
    await asyncio.wait_for(started.wait(), timeout=1)
    queue.enqueue(QueueEntry(workflow_id="B", reason="earlier"))
    queue.enqueue(QueueEntry(workflow_id="B", reason="latest"))
    release.set()
    await asyncio.wait_for(queue._task, timeout=1)

    assert batches == [[("A", "first")], [("B", "latest")]]
    assert queue.depth() == 0
    assert max_active == 1


@pytest.mark.asyncio
async def test_stop_cancels_pending_work_and_allows_restart():
    batches = []

    async def process(batch):
        batches.append(batch)

    queue = FleetManagerQueue(process, debounce_ms=0)
    queue.enqueue(QueueEntry(workflow_id="A", reason="cancelled"))
    await queue.stop()

    assert batches == []
    assert queue.depth() == 0
    queue.enqueue(QueueEntry(workflow_id="B", reason="after-restart"))
    await asyncio.wait_for(queue._task, timeout=1)
    assert [entry.workflow_id for entry in batches[0]] == ["B"]


@pytest.mark.asyncio
async def test_stop_waits_for_active_batch_cancellation():
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def process(batch):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    queue = FleetManagerQueue(process, debounce_ms=0)
    queue.enqueue(QueueEntry(workflow_id="A", reason="active"))
    await asyncio.wait_for(started.wait(), timeout=1)

    await queue.stop()

    assert stopped.is_set()
    assert not queue._flushing
    assert queue.depth() == 0
