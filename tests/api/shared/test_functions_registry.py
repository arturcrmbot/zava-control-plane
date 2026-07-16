"""TASK-005 — FUNCTIONS registry sanity checks."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.shared import functions as fmod
from api.shared.functions import FUNCTIONS, PersonaTree
from api.shared.domains import DOMAINS


REPO_ROOT = Path(__file__).resolve().parents[3]
PERSONAE_DIR = REPO_ROOT / "api" / "server" / "personae"

EXPECTED_KEYS = {
    "finance", "hr", "revenue", "ops", "legal",
    "marketing", "tech", "data", "ceo", "legacy",
}


def test_ten_agency_function_keys():
    assert set(FUNCTIONS.keys()) == EXPECTED_KEYS


def test_non_legacy_have_owns_domains_or_kpis_minimums():
    """Non-legacy functions must have at least one KPI. Some functions
    have no domains owned yet (revenue, ops, data, customer-success);
    Phase 4 graduates synthetic-journey domains for them. So we only
    assert KPI presence + the documented owns_domains for the four
    that have them today."""
    expect_domains = {"finance", "hr", "legal", "marketing", "tech"}
    for name, fn in FUNCTIONS.items():
        if name == "legacy":
            continue
        assert len(fn.kpis) >= 1, f"{name} has no KPIs"
        if name in expect_domains:
            assert len(fn.owns_domains) >= 1, f"{name} should own ≥1 domain"


def test_back_refs_populated():
    """Every domain in DOMAINS has its function back-ref set (none None)."""
    for wt, dom in DOMAINS.items():
        assert dom.function is not None, f"{wt} has no function back-ref"


def test_legacy_resolves_for_carryover_domains():
    assert DOMAINS["expense-claim"].function == "legacy"
    assert DOMAINS["hiring"].function == "legacy"


def test_owns_domains_back_ref_consistency():
    """Every domain a function claims back-references that function."""
    for fn_name, fn in FUNCTIONS.items():
        for d in fn.owns_domains:
            assert DOMAINS[d].function == fn_name


def _walk(node: PersonaTree):
    yield node.role
    for child in node.manages:
        yield from _walk(child)


def test_persona_hierarchy_roles_resolve():
    for fn_name, fn in FUNCTIONS.items():
        for role in _walk(fn.persona_hierarchy):
            if role == "__legacy__":
                continue
            skill = PERSONAE_DIR / role / "SKILL.md"
            assert skill.is_file(), f"{fn_name} references missing persona '{role}'"
