"""portal_seed.seed_demo_reqs: materialise one Workflow per req fixture row.

The fixture lives at data/synthetic/hiring/reqs.json and lists the three
demo reqs the candidate portal /apply form posts. After seeding, the
StateStore.attach_candidate_to_role(role_id, ...) lookup must resolve.
"""
from __future__ import annotations

import asyncio
import pytest

from api.server.services import portal_seed
from api.server.services.event_bus import EventBus
from api.server.services.portal_seed import seed_demo_reqs
from api.server.services.state_store import StateStore


class _FakeAppState:
    def __init__(self) -> None:
        self.bus = EventBus()
        self.store = StateStore()


@pytest.fixture(autouse=True)
def _stub_durable_client(monkeypatch):
    """seed_demo_reqs schedules a HiringOrchestrator instance per req.
    Unit tests don't have a Functions host — stub the call so we exercise
    the upsert + role_id index path without network."""
    async def _fake_schedule(payload, function_name="HiringOrchestrator"):
        return {"id": f"fake-instance-{payload['workflow_id']}"}
    monkeypatch.setattr(portal_seed, "schedule_new_orchestration", _fake_schedule)


def test_seed_creates_three_workflows_with_role_id_index():
    state = _FakeAppState()
    spawned = asyncio.run(seed_demo_reqs(state))
    assert len(spawned) == 3
    # Each role_id from the fixture resolves to a workflow.
    for role_id in ("REQ-SDE-USA-DEMO", "REQ-SDE-DE-DEMO", "REQ-CD-USA-DEMO"):
        wid = state.store.attach_candidate_to_role(
            role_id, {"id": "C-X", "name": "X", "email": "x@x", "cv_url": ""},
        )
        assert wid is not None, f"role_id {role_id} did not resolve to a workflow"


def test_seed_is_idempotent_on_rerun():
    state = _FakeAppState()
    first = asyncio.run(seed_demo_reqs(state))
    second = asyncio.run(seed_demo_reqs(state))
    assert first == second
    # Total workflow count unchanged after the second pass.
    assert len(state.store.list_workflows()) == 3


def test_seed_writes_role_id_into_metadata():
    state = _FakeAppState()
    asyncio.run(seed_demo_reqs(state))
    workflows = state.store.list_workflows()
    role_ids = {w.metadata["role_id"] for w in workflows}
    assert role_ids == {
        "REQ-SDE-USA-DEMO",
        "REQ-SDE-DE-DEMO",
        "REQ-CD-USA-DEMO",
    }
    # demo_seed flag is set so cleanup logic / fleet manager can skip them.
    assert all(w.metadata.get("demo_seed") is True for w in workflows)
