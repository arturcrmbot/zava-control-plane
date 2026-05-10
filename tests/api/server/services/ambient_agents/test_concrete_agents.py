"""Phase 3 IP6 — TASK-034..-038. Concrete ambient agents validation."""
from __future__ import annotations

import pathlib
import tempfile

import pytest

from api.server.services.ambient_agents import (
    AMBIENT_AGENTS,
    BusTrigger,
    CypherTrigger,
)
from api.server.services.ambient_agents.finance import (
    BudgetVarianceWatcher,
    VendorRiskWatcher,
)
from api.server.services.ambient_agents.tech import AccessAnomalyWatcher
from api.server.services.ambient_dispatcher import _eval_filter
from api.shared.functions import FUNCTIONS


CONCRETE = (BudgetVarianceWatcher, VendorRiskWatcher, AccessAnomalyWatcher)


def test_all_three_concrete_agents_discovered():
    """All 3 concrete agents are registered in the AMBIENT_AGENTS dict."""
    for agent in CONCRETE:
        assert agent.name in AMBIENT_AGENTS, (
            f"{agent.name} missing from AMBIENT_AGENTS"
        )
        assert AMBIENT_AGENTS[agent.name] is agent


def test_each_agent_function_resolves_in_FUNCTIONS():
    for agent in CONCRETE:
        assert agent.function in FUNCTIONS, (
            f"{agent.name} declares unknown function {agent.function!r}"
        )


def test_each_agent_name_listed_under_its_function():
    for agent in CONCRETE:
        listed = FUNCTIONS[agent.function].ambient_agents
        assert agent.name in listed, (
            f"{agent.name} not in FUNCTIONS[{agent.function!r}].ambient_agents={listed!r}"
        )


@pytest.mark.parametrize("agent", [BudgetVarianceWatcher, VendorRiskWatcher])
def test_cypher_trigger_pattern_parses_against_empty_graph(agent, tmp_path):
    """The Cypher pattern is well-formed: an empty graph returns [] not raise."""
    from api.server.services.entity_graph import EntityGraph

    g = EntityGraph(tmp_path / f"{agent.name}.kuzu")
    try:
        for trigger in agent.triggers:
            assert isinstance(trigger, CypherTrigger)
            rows = g.query(trigger.pattern)
            assert rows == []
    finally:
        g.close()


def test_access_anomaly_filter_safe_evals():
    """AccessAnomalyWatcher's BusTrigger filter compiles + evaluates cleanly
    via the dispatcher's safe-eval helper. We verify both the True path
    (it-access-request approved) and the False path (other workflow_type).
    """
    (trigger,) = AccessAnomalyWatcher.triggers
    assert isinstance(trigger, BusTrigger)

    # True path
    ctx_true = {
        "payload": {
            "workflow_type": "it-access-request",
            "decision_outcome": {"verdict": "approved"},
        }
    }
    assert _eval_filter(trigger.filter, ctx_true) is True

    # False path — different workflow type
    ctx_false_wt = {
        "payload": {
            "workflow_type": "vendor-kyc",
            "decision_outcome": {"verdict": "approved"},
        }
    }
    assert _eval_filter(trigger.filter, ctx_false_wt) is False

    # False path — wrong verdict
    ctx_false_verdict = {
        "payload": {
            "workflow_type": "it-access-request",
            "decision_outcome": {"verdict": "rejected"},
        }
    }
    assert _eval_filter(trigger.filter, ctx_false_verdict) is False


def test_spawnable_workflow_types_documented_as_forward_declared():
    """variance-investigation and access-review are forward-declared
    workflow_types not yet present in DOMAINS. The dispatcher's spawn
    path must skip rather than crash on them.
    """
    from api.shared.domains import DOMAINS
    expected_forward = {"variance-investigation", "access-review"}
    declared = set()
    for agent in CONCRETE:
        declared.update(agent.spawnable_workflow_types)
    forward = declared - set(DOMAINS.keys())
    # vendor-kyc IS a registered domain; the other two are not
    assert "vendor-kyc" not in forward
    assert expected_forward.issubset(forward)
