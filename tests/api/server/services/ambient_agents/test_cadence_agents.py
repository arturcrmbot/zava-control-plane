"""Phase 4 IP1 (TASK-006b) — cadence-trigger ambient agents discovered."""
from __future__ import annotations

from pathlib import Path

from api.server.services.ambient_agents import (
    AMBIENT_AGENTS,
    CadenceTrigger,
    agents_by_trigger_kind,
)
from api.server.services.cadence_loader import load_cadences
from api.shared.functions import FUNCTIONS


CADENCE_AGENTS = ("morning-sweep", "period-close", "quarterly-okr")


def test_three_cadence_agents_discovered():
    for name in CADENCE_AGENTS:
        assert name in AMBIENT_AGENTS, (
            f"cadence agent {name!r} missing from AMBIENT_AGENTS"
        )


def test_each_cadence_agent_listed_under_its_function():
    expected = {
        "morning-sweep": "hr",
        "period-close": "finance",
        "quarterly-okr": "ceo",
    }
    for name, fn in expected.items():
        agent = AMBIENT_AGENTS[name]
        assert agent.function == fn
        assert name in FUNCTIONS[fn].ambient_agents


def test_each_cadence_agent_carries_a_cadence_trigger():
    for name in CADENCE_AGENTS:
        agent = AMBIENT_AGENTS[name]
        assert any(isinstance(t, CadenceTrigger) for t in agent.triggers)


def test_cadence_yamls_resolve_to_real_ambient_agents():
    """Each shipped cadence YAML's ``fires_ambient_agent`` resolves to
    an actual AmbientAgent declared in AMBIENT_AGENTS."""
    repo_root = Path(__file__).resolve().parents[5]
    cadence_dir = repo_root / "data" / "governance" / "cadences"
    cads = load_cadences(cadence_dir)
    assert {c.name for c in cads} == set(CADENCE_AGENTS)
    for cad in cads:
        assert cad.fires_ambient_agent in AMBIENT_AGENTS, (
            f"cadence {cad.name} fires unknown agent {cad.fires_ambient_agent!r}"
        )


def test_agents_by_trigger_kind_returns_cadence_agents():
    cadence_agents = {a.name for a in agents_by_trigger_kind("cadence")}
    for name in CADENCE_AGENTS:
        assert name in cadence_agents
