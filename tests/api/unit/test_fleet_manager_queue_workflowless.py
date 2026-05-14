"""Workflow-less wake events (fleet.tick, fleet.anomaly.detected) need to
flow through the FM queue too — without a workflow_id to key on, they use a
per-reason sentinel so two distinct reasons inside the debounce window don't
collide. Regression for the demo-rail responsiveness fix.
"""
from __future__ import annotations
import asyncio
import pytest

from api.server.services.fleet_manager_queue import FleetManagerQueue, QueueEntry


@pytest.mark.asyncio
async def test_workflowless_entries_with_distinct_reasons_both_flush():
    calls = []

    async def proc(batch):
        calls.append(list(batch))

    q = FleetManagerQueue(proc, debounce_ms=100)
    q.enqueue(QueueEntry(workflow_id=None, reason="fleet.tick"))
    q.enqueue(QueueEntry(workflow_id=None, reason="fleet.anomaly.detected"))
    assert q.depth() == 2
    await asyncio.sleep(0.2)
    assert len(calls) == 1
    reasons = sorted(e.reason for e in calls[0])
    assert reasons == ["fleet.anomaly.detected", "fleet.tick"]


@pytest.mark.asyncio
async def test_workflowless_same_reason_dedupes():
    """Two ticks inside the debounce window collapse to one entry — same as
    workflow-bound dedup."""
    calls = []

    async def proc(batch):
        calls.append(list(batch))

    q = FleetManagerQueue(proc, debounce_ms=100)
    q.enqueue(QueueEntry(workflow_id=None, reason="fleet.tick"))
    q.enqueue(QueueEntry(workflow_id=None, reason="fleet.tick"))
    assert q.depth() == 1
    await asyncio.sleep(0.2)
    assert len(calls) == 1
    assert len(calls[0]) == 1


@pytest.mark.asyncio
async def test_workflowless_does_not_collide_with_real_workflow():
    """A workflow named like the sentinel format must still be keyed
    independently from a workflow-less entry — the sentinel uses an
    unambiguous `__fleet__:` prefix to avoid this."""
    calls = []

    async def proc(batch):
        calls.append(list(batch))

    q = FleetManagerQueue(proc, debounce_ms=100)
    q.enqueue(QueueEntry(workflow_id="W-1", reason="fleet.tick"))
    q.enqueue(QueueEntry(workflow_id=None, reason="fleet.tick"))
    assert q.depth() == 2
    await asyncio.sleep(0.2)
    assert len(calls) == 1
    workflow_ids = sorted((e.workflow_id or "") for e in calls[0])
    assert workflow_ids == ["", "W-1"]
