"""Tests for api.server.data_fabric.employee_gen.

Plan: plan/feature-enterprise-pitch-readiness-1.md (task ``pitch-b2``).
"""
from __future__ import annotations

from datetime import date

from api.server.data_fabric.employee_gen import (
    SUBSIDIARIES,
    GeneratedEmployee,
    generate_employees,
)
from api.shared.functions import FUNCTIONS


def test_generate_returns_exact_count() -> None:
    emps = generate_employees(seed=42, count=100)
    assert len(emps) == 100
    assert all(isinstance(e, GeneratedEmployee) for e in emps)


def test_ids_are_unique_and_well_formed() -> None:
    emps = generate_employees(seed=42, count=100)
    ids = [e.id for e in emps]
    assert len(set(ids)) == len(ids)
    for eid in ids:
        assert eid.startswith("PERSON-EMP-")


def test_determinism_same_seed_same_output() -> None:
    a = generate_employees(seed=42, count=100)
    b = generate_employees(seed=42, count=100)
    assert a == b


def test_different_seed_changes_output() -> None:
    a = generate_employees(seed=42, count=100)
    b = generate_employees(seed=43, count=100)
    assert a != b


def test_manager_chain_resolves() -> None:
    emps = generate_employees(seed=42, count=100)
    by_id = {e.id: e for e in emps}
    for e in emps:
        if e.manager_id is not None:
            assert e.manager_id in by_id, f"{e.id} has dangling manager {e.manager_id}"
            # Manager belongs to the same function (org-chart spine is per-function).
            assert by_id[e.manager_id].function == e.function


def test_subsidiary_is_one_of_five() -> None:
    emps = generate_employees(seed=42, count=100)
    for e in emps:
        assert e.subsidiary in SUBSIDIARIES


def test_at_least_one_person_per_function() -> None:
    emps = generate_employees(seed=42, count=100)
    seen = {e.function for e in emps}
    for fn_name in FUNCTIONS:
        assert fn_name in seen, f"no employee generated for function {fn_name}"


def test_employed_from_in_range() -> None:
    emps = generate_employees(seed=42, count=100)
    today = date.today()
    for e in emps:
        assert date(2020, 1, 1) <= e.employed_from <= today


def test_sorted_by_id() -> None:
    emps = generate_employees(seed=42, count=100)
    assert [e.id for e in emps] == sorted(e.id for e in emps)


def test_email_uniqueness() -> None:
    emps = generate_employees(seed=42, count=100)
    emails = [e.email for e in emps]
    assert len(set(emails)) == len(emails)
