"""TASK-006 — failure-path tests for the function registry validators."""
from __future__ import annotations

import pytest

from api.shared import functions as fmod
from api.shared.functions import (
    FUNCTIONS,
    Function,
    PersonaTree,
    _validate_persona_hierarchy,
    _wire_function_back_refs,
)
from api.shared.domains import DOMAINS


def _reset_back_refs() -> None:
    for d in DOMAINS.values():
        d.function = None


def test_unknown_domain_raises(monkeypatch):
    bad = Function(
        name="finance", display="Finance", operator_surface="x",
        owns_domains=("nope-not-a-real-domain",),
        ambient_agents=(), kpis=("k",),
        persona_hierarchy=PersonaTree(role="cfo"),
    )
    fake = dict(FUNCTIONS)
    fake["finance"] = bad
    monkeypatch.setattr(fmod, "FUNCTIONS", fake)
    _reset_back_refs()
    try:
        with pytest.raises(ValueError, match="claims unknown domain"):
            _wire_function_back_refs()
    finally:
        # Re-wire from the real registry so subsequent tests see proper back-refs.
        monkeypatch.undo()
        _reset_back_refs()
        _wire_function_back_refs()


def test_orphan_domain_raises(monkeypatch):
    """Removing legacy claims orphans expense-claim + hiring."""
    stripped_legacy = Function(
        name="legacy", display="Legacy", operator_surface="x",
        owns_domains=(),  # no longer claims expense-claim/hiring
        ambient_agents=(), kpis=(),
        persona_hierarchy=PersonaTree(role="__legacy__"),
    )
    fake = dict(FUNCTIONS)
    fake["legacy"] = stripped_legacy
    monkeypatch.setattr(fmod, "FUNCTIONS", fake)
    _reset_back_refs()
    try:
        with pytest.raises(ValueError, match="unclaimed domains"):
            _wire_function_back_refs()
    finally:
        monkeypatch.undo()
        _reset_back_refs()
        _wire_function_back_refs()


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
