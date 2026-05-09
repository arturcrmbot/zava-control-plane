"""TASK-011 — AmbientAgent primitive + module discovery."""
from __future__ import annotations

import pytest

from api.server.services.ambient_agents import (
    AMBIENT_AGENTS,
    AmbientAgent,
    BusTrigger,
    CadenceTrigger,
    CypherTrigger,
    Trigger,
    _discover_ambient_agents,
    agents_by_trigger_kind,
    agents_for_function,
)


def test_trigger_kind_discriminators():
    b = BusTrigger(event_type="workflow.completed")
    c = CypherTrigger(pattern="MATCH (n) RETURN n", sweep_seconds=10)
    d = CadenceTrigger(cron="0 9 * * *")
    assert b.kind == "bus"
    assert c.kind == "cypher"
    assert d.kind == "cadence"


def test_ambient_agent_accepts_heterogeneous_triggers():
    agent = AmbientAgent(
        name="test-agent", function="finance",
        triggers=(BusTrigger(event_type="x"), CypherTrigger(pattern="y")),
    )
    assert agent.triggers[0].kind == "bus"
    assert agent.triggers[1].kind == "cypher"


def test_discovery_empty_before_phase_6():
    """Before TASK-035..-037 plant concrete declarations, discovery
    returns an empty dict (the per-function modules are stubs)."""
    found = _discover_ambient_agents()
    assert found == {}
    assert AMBIENT_AGENTS == {}


def test_unknown_function_loud_failure(monkeypatch):
    """An AmbientAgent whose .function is not in FUNCTIONS must fail at discovery."""
    import sys, types, pkgutil
    from api.server.services import ambient_agents as ambient_pkg

    fake_mod_name = f"{ambient_pkg.__name__}.fake_unknown_fn_test"
    mod = types.ModuleType(fake_mod_name)
    mod.bad_agent = AmbientAgent(  # type: ignore[attr-defined]
        name="x", function="not-a-real-function",
        triggers=(BusTrigger(event_type="y"),),
    )
    sys.modules[fake_mod_name] = mod

    class _MI:
        def __init__(self, name): self.name = name

    monkeypatch.setattr(pkgutil, "iter_modules", lambda paths: [_MI("fake_unknown_fn_test")])
    try:
        with pytest.raises(ValueError, match="not in FUNCTIONS"):
            _discover_ambient_agents()
    finally:
        sys.modules.pop(fake_mod_name, None)


def test_unknown_name_loud_failure(monkeypatch):
    """An AmbientAgent whose .name isn't in FUNCTIONS[fn].ambient_agents must fail."""
    import sys, types, pkgutil
    from api.server.services import ambient_agents as ambient_pkg

    fake_mod_name = f"{ambient_pkg.__name__}.fake_unknown_name_test"
    mod = types.ModuleType(fake_mod_name)
    mod.bad_agent = AmbientAgent(  # type: ignore[attr-defined]
        name="not-listed-in-finance-ambient-agents",
        function="finance",
        triggers=(BusTrigger(event_type="y"),),
    )
    sys.modules[fake_mod_name] = mod

    class _MI:
        def __init__(self, name): self.name = name

    monkeypatch.setattr(pkgutil, "iter_modules", lambda paths: [_MI("fake_unknown_name_test")])
    try:
        with pytest.raises(ValueError, match="not listed"):
            _discover_ambient_agents()
    finally:
        sys.modules.pop(fake_mod_name, None)


def test_helpers_with_seeded_registry(monkeypatch):
    """agents_for_function + agents_by_trigger_kind walk AMBIENT_AGENTS."""
    from api.server.services import ambient_agents as ambient_pkg

    seeded = {
        "fin-bus": AmbientAgent(
            name="fin-bus", function="finance",
            triggers=(BusTrigger(event_type="workflow.completed"),),
        ),
        "fin-cyp": AmbientAgent(
            name="fin-cyp", function="finance",
            triggers=(CypherTrigger(pattern="MATCH (n) RETURN n"),),
        ),
        "tech-cad": AmbientAgent(
            name="tech-cad", function="tech",
            triggers=(CadenceTrigger(cron="0 9 * * *"),),
        ),
    }
    monkeypatch.setattr(ambient_pkg, "AMBIENT_AGENTS", seeded)
    fin = agents_for_function("finance")
    assert {a.name for a in fin} == {"fin-bus", "fin-cyp"}
    bus = agents_by_trigger_kind("bus")
    cad = agents_by_trigger_kind("cadence")
    assert {a.name for a in bus} == {"fin-bus"}
    assert {a.name for a in cad} == {"tech-cad"}
