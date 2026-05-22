"""MutationBus: a tee that records state mutations when active."""

from typing import Any


class MutationBus:
    """Records state mutations (op, kind, id, patch) as they occur."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def emit(self, *, op: str, kind: str, id: str, patch: dict[str, Any]) -> None:
        """Record a mutation."""
        self.entries.append({"op": op, "kind": kind, "id": id, "patch": patch})


_active: MutationBus | None = None


def set_active_bus(bus: MutationBus | None) -> None:
    """Set the active global mutation bus (or None to deactivate)."""
    global _active
    _active = bus


def get_active_bus() -> MutationBus | None:
    """Get the active global mutation bus (or None if none is active)."""
    return _active


def emit_mutation(*, op: str, kind: str, id: str, patch: dict[str, Any]) -> None:
    """Emit a mutation to the active bus if one exists.
    
    Wraps in try/except to ensure bus failures never break state writes.
    This is a noop if no bus is active.
    """
    bus = get_active_bus()
    if bus is None:
        return
    try:
        bus.emit(op=op, kind=kind, id=id, patch=patch)
    except Exception:
        # Never let a mutation tap break a state write
        pass
