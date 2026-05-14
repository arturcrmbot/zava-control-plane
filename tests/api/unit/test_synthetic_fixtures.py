"""Shape and invariant tests for the static synthetic fixtures."""
from __future__ import annotations
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data" / "synthetic"


def test_employees_json_shape():
    employees = json.loads((DATA / "employees.json").read_text(encoding="utf-8"))
    assert isinstance(employees, list)
    assert len(employees) >= 25, "need a small population (>=25)"
    repeat_offenders = [e for e in employees if e.get("breach_history") and len(e["breach_history"]) >= 2]
    assert len(repeat_offenders) >= 3, "spec §5.4 requires >=3 repeat-offender profiles"
    for e in employees:
        assert {"id", "name", "market", "department", "agency", "breach_history"} <= set(e), f"missing keys on {e.get('id')!r}"
        assert e["market"] in {"UK", "US", "DE", "IN"}, e["market"]
        for b in e["breach_history"]:
            assert {"date", "category", "tier"} <= set(b), b


def test_precedents_json_shape():
    precedents = json.loads((DATA / "precedents.json").read_text(encoding="utf-8"))
    assert isinstance(precedents, list)
    assert len(precedents) >= 50, "spec §5.4 requires ~50 historical decisions"
    for p in precedents:
        assert {"id", "claim_summary", "policy_clause", "reviewer_decision", "rationale", "decided_at"} <= set(p), p
        assert p["reviewer_decision"] in {"accept-justification", "require-repayment", "issue-warning", "escalate"}
