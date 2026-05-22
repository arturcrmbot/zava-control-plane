"""Tests for MutationBus."""

import pytest

from api.server.services.replay.mutation_bus import (
    MutationBus,
    emit_mutation,
    get_active_bus,
    set_active_bus,
)


def teardown_function() -> None:
    """Clean up active bus after each test."""
    set_active_bus(None)


def test_get_active_bus_returns_none_by_default() -> None:
    """get_active_bus() should return None when no bus is set."""
    assert get_active_bus() is None


def test_emit_mutation_noop_when_no_bus() -> None:
    """emit_mutation should be a noop when no bus is active."""
    # Should not raise, should not crash
    emit_mutation(op="upsert", kind="workflow", id="w1", patch={"status": "active"})


def test_set_active_bus_activates() -> None:
    """set_active_bus() should activate a bus."""
    bus = MutationBus()
    set_active_bus(bus)
    assert get_active_bus() is bus


def test_emit_mutation_lands_entry_on_bus() -> None:
    """emit_mutation should add entries to the active bus."""
    bus = MutationBus()
    set_active_bus(bus)
    
    emit_mutation(op="upsert", kind="workflow", id="w1", patch={"status": "active"})
    
    assert len(bus.entries) == 1
    assert bus.entries[0] == {
        "op": "upsert",
        "kind": "workflow",
        "id": "w1",
        "patch": {"status": "active"},
    }


def test_entries_carry_exact_fields() -> None:
    """Entries should carry op, kind, id, patch exactly as passed."""
    bus = MutationBus()
    set_active_bus(bus)
    
    patch = {"name": "test", "nested": {"value": 42}}
    emit_mutation(op="delete", kind="memory", id="mem123", patch=patch)
    
    assert bus.entries[0]["op"] == "delete"
    assert bus.entries[0]["kind"] == "memory"
    assert bus.entries[0]["id"] == "mem123"
    assert bus.entries[0]["patch"] == patch


def test_set_active_bus_none_clears_it() -> None:
    """set_active_bus(None) should clear the active bus."""
    bus = MutationBus()
    set_active_bus(bus)
    assert get_active_bus() is bus
    
    set_active_bus(None)
    assert get_active_bus() is None


def test_emit_mutation_noop_after_clear() -> None:
    """emit_mutation should be a noop after clearing the active bus."""
    bus = MutationBus()
    set_active_bus(bus)
    
    emit_mutation(op="upsert", kind="workflow", id="w1", patch={})
    assert len(bus.entries) == 1
    
    set_active_bus(None)
    emit_mutation(op="upsert", kind="workflow", id="w2", patch={})
    
    # Bus should still have only 1 entry
    assert len(bus.entries) == 1


def test_bus_emit_exception_is_swallowed() -> None:
    """emit_mutation should swallow exceptions from bus.emit()."""
    class FailingBus(MutationBus):
        def emit(self, *, op: str, kind: str, id: str, patch: dict) -> None:
            raise RuntimeError("Bus failure!")
    
    bus = FailingBus()
    set_active_bus(bus)
    
    # Should not raise, should silently swallow the exception
    emit_mutation(op="upsert", kind="workflow", id="w1", patch={})


def test_multiple_mutations_accumulate() -> None:
    """Multiple emit_mutation calls should accumulate entries."""
    bus = MutationBus()
    set_active_bus(bus)
    
    emit_mutation(op="upsert", kind="workflow", id="w1", patch={"v": 1})
    emit_mutation(op="delete", kind="memory", id="m1", patch={})
    emit_mutation(op="upsert", kind="decision", id="d1", patch={"x": "y"})
    
    assert len(bus.entries) == 3
    assert bus.entries[0]["kind"] == "workflow"
    assert bus.entries[1]["kind"] == "memory"
    assert bus.entries[2]["kind"] == "decision"


def test_bus_emit_direct_call() -> None:
    """MutationBus.emit() should work directly."""
    bus = MutationBus()
    bus.emit(op="upsert", kind="workflow", id="w1", patch={"status": "active"})
    
    assert len(bus.entries) == 1
    assert bus.entries[0] == {
        "op": "upsert",
        "kind": "workflow",
        "id": "w1",
        "patch": {"status": "active"},
    }


def test_different_kinds() -> None:
    """Test that different kinds are preserved."""
    bus = MutationBus()
    set_active_bus(bus)
    
    kinds = ["workflow", "exception", "memory", "lesson", "decision", "insight", "entity", "audit"]
    for i, kind in enumerate(kinds):
        emit_mutation(op="upsert", kind=kind, id=f"id{i}", patch={})
    
    assert len(bus.entries) == len(kinds)
    for i, kind in enumerate(kinds):
        assert bus.entries[i]["kind"] == kind


def test_both_ops() -> None:
    """Test that both ops (upsert and delete) are preserved."""
    bus = MutationBus()
    set_active_bus(bus)
    
    emit_mutation(op="upsert", kind="workflow", id="w1", patch={})
    emit_mutation(op="delete", kind="workflow", id="w1", patch={})
    
    assert bus.entries[0]["op"] == "upsert"
    assert bus.entries[1]["op"] == "delete"


def test_drain_returns_entries_and_clears_buffer() -> None:
    bus = MutationBus()
    bus.emit(op="upsert", kind="workflow", id="w1", patch={"status": "active"})
    bus.emit(op="delete", kind="memory", id="m1", patch={})

    drained = bus.drain()

    assert drained == [
        {"op": "upsert", "kind": "workflow", "id": "w1", "patch": {"status": "active"}},
        {"op": "delete", "kind": "memory", "id": "m1", "patch": {}},
    ]
    assert bus.entries == []
