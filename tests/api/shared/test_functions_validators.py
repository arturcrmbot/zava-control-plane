"""TASK-006 — failure-path tests for the function-ownership registry validators.

Function → domain wiring now happens once, while building the selected
pack, via ``verticals._helpers.wire_domain_functions`` (a pure function —
no boot-time mutation of a global domain dictionary). These tests exercise
its failure paths directly. Persona-hierarchy validation is exercised via
``api.shared.functions._validate_persona_hierarchy``, which still reads the
active pack's ``FUNCTIONS`` mapping and personae roots.
"""
from __future__ import annotations

import pytest

from api.shared import functions as fmod
from api.shared.domain_contracts import Domain, Phase
from api.shared.function_contracts import Function, PersonaTree
from api.shared.functions import FUNCTIONS, _validate_persona_hierarchy
from verticals._helpers import wire_domain_functions


def _domain(workflow_type: str) -> Domain:
    return Domain(
        workflow_type=workflow_type,
        display_name=workflow_type,
        workflow_id_prefix=workflow_type.upper()[:4],
        orchestrator_name="DemoOrchestrator",
        operator_surface="demo",
        phases=(Phase("Intake", "deterministic"),),
        hitl_gates=(),
        skills=(),
    )


def _function(name: str, *owned_domains: str, role: str = "cfo") -> Function:
    return Function(
        name=name,
        display=name,
        operator_surface="x",
        owns_domains=owned_domains,
        ambient_agents=(),
        kpis=("k",),
        persona_hierarchy=PersonaTree(role=role),
    )


def test_unknown_domain_claim_raises():
    """A function claiming a domain absent from the domain mapping fails
    with the claimed workflow_type surfaced under ``unknown=``."""
    domains = {"expense-claim": _domain("expense-claim")}
    functions = {
        "finance": _function("finance", "nope-not-a-real-domain"),
    }
    with pytest.raises(ValueError, match=r"unknown=\['nope-not-a-real-domain'\]"):
        wire_domain_functions(domains, functions)


def test_orphan_domain_raises():
    """A domain no function claims fails with it surfaced under ``missing=``."""
    domains = {
        "expense-claim": _domain("expense-claim"),
        "hiring": _domain("hiring"),
    }
    functions = {
        "legacy": _function("legacy", "expense-claim", role="__legacy__"),
    }
    with pytest.raises(ValueError, match=r"missing=\['hiring'\]"):
        wire_domain_functions(domains, functions)


def test_duplicate_owner_raises():
    """Two functions claiming the same domain fails loudly and immediately."""
    domains = {"expense-claim": _domain("expense-claim")}
    functions = {
        "legacy": _function("legacy", "expense-claim", role="__legacy__"),
        "finance": _function("finance", "expense-claim"),
    }
    with pytest.raises(ValueError, match="multiple function owners"):
        wire_domain_functions(domains, functions)


def test_wiring_stamps_function_back_ref():
    """The happy path: every domain comes back with its owner's name."""
    domains = {"expense-claim": _domain("expense-claim")}
    functions = {"legacy": _function("legacy", "expense-claim", role="__legacy__")}

    wired = wire_domain_functions(domains, functions)

    assert wired["expense-claim"].function == "legacy"


def test_unknown_persona_raises(monkeypatch):
    bad = Function(
        name="finance", display="Finance", operator_surface="x",
        owns_domains=FUNCTIONS["finance"].owns_domains,
        ambient_agents=(), kpis=("dso",),
        persona_hierarchy=PersonaTree(role="not_a_real_persona_xyz"),
    )
    fake = dict(FUNCTIONS)
    fake["finance"] = bad
    monkeypatch.setattr(fmod, "FUNCTIONS", fake)
    with pytest.raises(ValueError, match="references unknown persona"):
        _validate_persona_hierarchy()
