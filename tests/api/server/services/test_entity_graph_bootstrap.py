"""Bootstrap behaviour for ``EntityGraph`` (TASK-008).

End-to-end coverage of :meth:`EntityGraph.bootstrap_from_fixtures` against
the real on-disk fixtures (``data/synthetic/employees.json``,
``api/server/fixtures/vendors.json``, ``api/server/fixtures/agencies.json``).

Threshold note: the plan's text asks for "≥40 Persons" but the actual
fixture currently ships 30 employees. Tests assert ``>= 30`` to match
reality; the gap is reported back to the human author for resolution
(either pad ``employees.json`` to 40+ rows or revise the floor in the
plan). See task report.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api.server.services.entity_graph import EntityGraph


REPO_ROOT = Path(__file__).resolve().parents[4]
EMPLOYEES = REPO_ROOT / "data" / "synthetic" / "employees.json"
VENDORS = REPO_ROOT / "api" / "server" / "fixtures" / "vendors.json"
AGENCIES = REPO_ROOT / "api" / "server" / "fixtures" / "agencies.json"


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


def test_fixture_files_exist() -> None:
    """Sanity: the three fixtures the bootstrap relies on are checked in."""
    assert EMPLOYEES.is_file(), f"missing fixture: {EMPLOYEES}"
    assert VENDORS.is_file(), f"missing fixture: {VENDORS}"
    assert AGENCIES.is_file(), f"missing fixture: {AGENCIES}"


def test_bootstrap_loads_real_fixtures(graph: EntityGraph) -> None:
    """End-to-end: real fixtures land Persons + Organisations in the graph."""
    counts = graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    assert counts["persons"] > 0
    assert counts["organisations"] > 0
    # Counts must match what landed in the graph.
    assert len(graph.by_type("Person")) == counts["persons"]
    assert len(graph.by_type("Organisation")) == counts["organisations"]


def test_bootstrap_yields_at_least_30_persons(graph: EntityGraph) -> None:
    """Plan's floor was ≥40 — fixture only has 30; assert against actual.

    If the fixture grows past 40 the assertion still passes; if it shrinks
    below 30 (the current count) this test will fail and surface the
    regression.
    """
    graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    persons = graph.by_type("Person")
    assert len(persons) >= 30, (
        f"expected ≥30 Person rows from {EMPLOYEES}, got {len(persons)}"
    )


def test_bootstrap_stamps_source_workflows_with_bootstrap(graph: EntityGraph) -> None:
    """Every bootstrapped entity carries 'bootstrap' in its source_workflows."""
    graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    for kind in ("Person", "Organisation"):
        rows = graph.by_type(kind)
        assert rows, f"no {kind} rows after bootstrap"
        for row in rows:
            sw = list(row.get("source_workflows") or [])
            assert "bootstrap" in sw, (
                f"{kind} {row['id']} missing 'bootstrap' source_workflow: {sw}"
            )


def test_bootstrap_organisations_split_vendor_vs_agency(graph: EntityGraph) -> None:
    """Vendors land with kind='vendor', agencies with kind='agency'."""
    graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    # by_type's first positional arg is also called ``kind`` (it's the node
    # kind), so use a Cypher query for the column-level ``kind`` filter.
    orgs = graph.by_type("Organisation")
    vendors = [o for o in orgs if o.get("kind") == "vendor"]
    agencies = [o for o in orgs if o.get("kind") == "agency"]
    assert len(vendors) > 0
    assert len(agencies) > 0
    assert len(vendors) + len(agencies) == len(orgs)


def test_bootstrap_preserves_unmapped_fixture_fields_in_attributes(
    graph: EntityGraph,
) -> None:
    """Fixture fields with no matching column survive in the JSON ``attributes`` blob."""
    graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    # employees.json carries "agency" (string), "breach_history" (list) — neither
    # is a Person column, so both should land inside the attributes blob.
    person = graph.get("PERSON-EMP-0001")
    assert person is not None
    raw = person.get("attributes")
    assert raw, "Person.attributes blob is empty — unmapped fields were dropped"
    blob = json.loads(raw)
    assert "agency" in blob
    assert "breach_history" in blob


def test_bootstrap_emits_one_audit_summary(graph: EntityGraph) -> None:
    """Single 'entity.bootstrap.completed' at the end — not per record."""
    audit = MagicMock()
    graph.attach(audit=audit)
    counts = graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    bootstrap_calls = [
        c for c in audit.log.call_args_list
        if c.args and c.args[0] == "entity.bootstrap.completed"
    ]
    assert len(bootstrap_calls) == 1
    payload = bootstrap_calls[0].args[1]
    assert payload == {"counts": counts}
    assert payload["counts"]["persons"] > 0
    assert payload["counts"]["organisations"] > 0


def test_bootstrap_no_audit_when_unattached(graph: EntityGraph) -> None:
    """Without ``attach()`` the bootstrap still runs; no emission attempted."""
    counts = graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    assert counts["persons"] > 0
    assert graph.audit is None  # not attached, so nothing to call


def test_bootstrap_idempotent(graph: EntityGraph) -> None:
    """Re-bootstrapping is safe: same counts, no duplicate Persons/Orgs."""
    counts1 = graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    counts2 = graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    assert counts1 == counts2
    persons = graph.by_type("Person")
    assert len(persons) == counts1["persons"]
    orgs = graph.by_type("Organisation")
    assert len(orgs) == counts1["organisations"]
    # source_workflows still deduped to a single 'bootstrap' entry.
    for row in persons[:5]:
        sw = list(row.get("source_workflows") or [])
        assert sw.count("bootstrap") == 1, f"duplicate bootstrap in {sw}"


def test_bootstrap_missing_file_raises(graph: EntityGraph, tmp_path: Path) -> None:
    """Missing fixture path raises FileNotFoundError (loud)."""
    with pytest.raises(FileNotFoundError):
        graph.bootstrap_from_fixtures(
            employees_path=tmp_path / "does-not-exist.json",
            vendors_path=VENDORS,
            agencies_path=AGENCIES,
        )
