from __future__ import annotations

import time

import pytest

from api.server.services.memory.domain_memory import DomainMemory
from api.server.services.memory.fallback_memory import get_fallback_memory
from api.server.services.replay.mutation_bus import MutationBus, set_active_bus
from api.server.services.state_store import StateStore
from api.shared.types import Exception_ as Exception, Workflow


class RaisingBus(MutationBus):
    def emit(self, *, op: str, kind: str, id: str, patch: dict) -> None:
        raise RuntimeError("boom")


@pytest.fixture(autouse=True)
def _clear_active_bus() -> None:
    set_active_bus(None)
    yield
    set_active_bus(None)


@pytest.fixture
def domain_memory() -> DomainMemory:
    mem = DomainMemory(domain="test", memory=get_fallback_memory())
    mem.delete_all()
    yield mem
    mem.delete_all()


def _workflow(workflow_id: str = "WF-1") -> Workflow:
    now = time.time()
    return Workflow(
        id=workflow_id,
        type="hiring",
        current_phase="Triage",
        created_at=now,
        sla_due_at=now + 3600,
        jurisdiction="UK",
        agency="zava",
        metadata={"role_id": "role-1"},
    )


def _exception(workflow_id: str, exception_id: str = "EX-1") -> Exception:
    return Exception(
        id=exception_id,
        workflow_id=workflow_id,
        composed_by="deterministic",
        severity="medium",
        category="compliance",
        summary="Needs review",
        recommendation="Investigate",
        created_at=time.time(),
    )


def test_upsert_workflow_emits_one_mutation_with_active_bus() -> None:
    store = StateStore()
    workflow = _workflow()
    bus = MutationBus()
    set_active_bus(bus)

    store.upsert_workflow(workflow)

    assert len(bus.entries) == 1
    assert bus.entries[0]["op"] == "upsert"
    assert bus.entries[0]["kind"] == "workflow"
    assert bus.entries[0]["id"] == workflow.id
    assert "currentPhase" in bus.entries[0]["patch"]


def test_upsert_workflow_without_active_bus_emits_zero_mutations() -> None:
    store = StateStore()
    workflow = _workflow()
    bus = MutationBus()
    set_active_bus(bus)
    set_active_bus(None)

    store.upsert_workflow(workflow)

    assert bus.entries == []
    assert store.get_workflow(workflow.id) == workflow



def test_upsert_exception_emits_one_mutation_with_active_bus() -> None:
    store = StateStore()
    workflow = _workflow()
    store.upsert_workflow(workflow)
    bus = MutationBus()
    set_active_bus(bus)

    exc = _exception(workflow.id)
    store.upsert_exception(exc)

    assert len(bus.entries) == 1
    assert bus.entries[0]["op"] == "upsert"
    assert bus.entries[0]["kind"] == "exception"
    assert bus.entries[0]["id"] == exc.id


def test_domain_memory_add_working_emits_memory_mutation(domain_memory: DomainMemory) -> None:
    bus = MutationBus()
    set_active_bus(bus)

    results = domain_memory.add(
        "working note",
        agent_skill="triage",
        workflow_id="WF-1",
        kind="working",
        extra_metadata={"source": "test"},
    )

    assert len(results) >= 1
    assert len(bus.entries) == len(results)
    assert all(entry["kind"] == "memory" for entry in bus.entries)
    assert all(entry["op"] == "upsert" for entry in bus.entries)


def test_domain_memory_add_distilled_emits_lesson_mutation(domain_memory: DomainMemory) -> None:
    bus = MutationBus()
    set_active_bus(bus)

    results = domain_memory.add_distilled("distilled note", metadata={"source": "dream"})

    assert len(results) >= 1
    assert len(bus.entries) == len(results)
    assert all(entry["kind"] == "lesson" for entry in bus.entries)
    assert all(entry["op"] == "upsert" for entry in bus.entries)


def test_domain_memory_delete_emits_memory_delete(domain_memory: DomainMemory) -> None:
    stored = domain_memory.add("working note", workflow_id="WF-1")
    memory_id = stored[0]["id"]
    bus = MutationBus()
    set_active_bus(bus)

    domain_memory.delete(memory_id)

    assert bus.entries == [
        {
            "op": "delete",
            "kind": "memory",
            "id": memory_id,
            "patch": {"domain": "test"},
        }
    ]


def test_raising_bus_does_not_break_state_store_write() -> None:
    store = StateStore()
    workflow = _workflow()
    set_active_bus(RaisingBus())

    store.upsert_workflow(workflow)

    assert store.get_workflow(workflow.id) == workflow
