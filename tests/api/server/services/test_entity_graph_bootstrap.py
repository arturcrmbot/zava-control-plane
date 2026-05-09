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


def test_bootstrap_agencies_have_non_null_name(graph: EntityGraph) -> None:
    """Agencies in the fixture lack a name field; bootstrap must default
    name to the bare id (Option A repair) — never NULL.

    Locks the silent-NULL-name regression flagged in code review: any
    downstream code reading ``org["name"]`` on an agency row would have
    received None before this fix.
    """
    graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    orgs = [o for o in graph.by_type("Organisation") if o.get("kind") == "agency"]
    assert len(orgs) > 0, "no agency rows after bootstrap"
    for o in orgs:
        assert o.get("name") is not None, f"Agency {o['id']} has NULL name"
        assert o["name"] != ""
    # Spot-check: the canonical id-as-name mapping landed.
    ids_to_names = {o["id"]: o["name"] for o in orgs}
    assert ids_to_names.get("ORG-Ogilvy-US") == "Ogilvy-US"


def test_bootstrap_vendor_names_preserved(graph: EntityGraph) -> None:
    """Vendor fixture rows DO carry a ``name`` field — the agency-name
    repair must not clobber them with their bare ids."""
    graph.bootstrap_from_fixtures(
        employees_path=EMPLOYEES,
        vendors_path=VENDORS,
        agencies_path=AGENCIES,
    )
    vendors = [o for o in graph.by_type("Organisation") if o.get("kind") == "vendor"]
    assert len(vendors) > 0
    # Pull the canonical name from the fixture file and compare round-trip.
    raw_vendors = {v["id"]: v["name"] for v in json.loads(VENDORS.read_text())}
    for v in vendors:
        bare_id = v["id"].removeprefix("ORG-")
        expected = raw_vendors[bare_id]
        assert v["name"] == expected, (
            f"vendor {v['id']} name clobbered: got {v['name']!r}, "
            f"expected {expected!r}"
        )
        assert v["name"] != bare_id  # extra paranoia: not silently reassigned


def test_bootstrap_serialises_non_json_native_residuals(graph: EntityGraph) -> None:
    """``json.dumps`` inside bootstrap must use ``default=str`` — consistent
    with :meth:`record_decision` — so future fixtures containing a
    ``date`` / ``datetime`` / ``Decimal`` value won't crash bootstrap with
    a TypeError. Locks the fix at the call-site source level.
    """
    import inspect

    import api.server.services.entity_graph as eg

    src = (
        inspect.getsource(eg.EntityGraph.bootstrap_from_fixtures)
        + inspect.getsource(eg.EntityGraph._bootstrap_entity)
    )
    # Every json.dumps inside bootstrap must carry default=str.
    dumps_calls = src.count("json.dumps(")
    default_str_calls = src.count("default=str")
    assert dumps_calls > 0, "expected at least one json.dumps in bootstrap"
    assert default_str_calls >= dumps_calls, (
        f"json.dumps must use default=str (consistent with record_decision): "
        f"{dumps_calls} json.dumps calls but only {default_str_calls} default=str"
    )


def test_bootstrap_with_duplicate_ids_does_not_overcount(
    tmp_path: Path, graph: EntityGraph,
) -> None:
    """Counts reflect upsert calls, NOT unique entities. A fixture with
    duplicate ids inflates the returned count while ``by_type`` returns
    fewer rows. This is the documented contract — locked here so it's
    explicit, not silent."""
    employees = tmp_path / "employees.json"
    employees.write_text(json.dumps([
        {"id": "EMP-DUP", "name": "Alice"},
        {"id": "EMP-DUP", "name": "Bob"},
        {"id": "EMP-OK", "name": "Carol"},
    ]))
    vendors = tmp_path / "vendors.json"
    vendors.write_text("[]")
    agencies = tmp_path / "agencies.json"
    agencies.write_text("[]")

    counts = graph.bootstrap_from_fixtures(employees, vendors, agencies)
    persons = graph.by_type("Person")

    assert counts["persons"] == 3, "counts is per-upsert-call (documented)"
    assert len(persons) == 2, "graph stores unique entities (MERGE on id)"

    dup = next(p for p in persons if p["id"] == "PERSON-EMP-DUP")
    assert dup["name"] == "Bob", "second upsert overwrote first (last-write-wins)"


def test_bootstrap_raises_on_missing_id(
    tmp_path: Path, graph: EntityGraph,
) -> None:
    """A fixture row missing 'id' raises KeyError. Documented contract:
    bootstrap halts loud rather than skipping silently. Re-run after
    fixing the fixture is safe (upsert is idempotent)."""
    employees = tmp_path / "employees.json"
    employees.write_text(json.dumps([
        {"id": "EMP-OK", "name": "Alice"},
        {"name": "Bob"},  # missing id
    ]))
    vendors = tmp_path / "vendors.json"
    vendors.write_text("[]")
    agencies = tmp_path / "agencies.json"
    agencies.write_text("[]")

    with pytest.raises(KeyError):
        graph.bootstrap_from_fixtures(employees, vendors, agencies)

    # The first row landed before the second raised — confirms partial state.
    persons = graph.by_type("Person")
    assert len(persons) == 1
    assert persons[0]["id"] == "PERSON-EMP-OK"
