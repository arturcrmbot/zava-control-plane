"""The Fashion org-brief must separate synthetic demo assumptions (the
thresholds, ratios and scale counts wired into the pack) from researched
facts and open uncertainties, with the synthetic boundary explicit."""
from pathlib import Path

import yaml


BRIEF_PATH = (
    Path(__file__).resolve().parents[3]
    / "verticals"
    / "fashion"
    / "org-brief.yaml"
)

EXPECTED_ASSUMPTION_IDS = {
    "transfer-value-approval-threshold",
    "transfer-quantity-approval-threshold",
    "demand-confidence-floor",
    "fairness-score-floor",
    "recovered-margin-over-transfer-cost",
    "safety-stock-buffer",
    "actor-world-scale",
}


def _brief() -> dict:
    return yaml.safe_load(BRIEF_PATH.read_text(encoding="utf-8"))


def test_brief_keeps_facts_uncertainties_and_sources() -> None:
    brief = _brief()

    assert {"meta", "facts", "uncertainties", "exclusions", "sources"} <= set(
        brief
    )
    # The synthetic boundary is still declared at the top and in exclusions.
    assert brief["meta"]["evidence_policy"] == (
        "source-backed-industry-facts-only"
    )
    exclusions = " ".join(brief["exclusions"]).lower()
    assert "no synthetic actor" in exclusions


def test_brief_declares_an_explicit_assumptions_section() -> None:
    brief = _brief()

    assert "assumptions" in brief, "org-brief must declare top-level assumptions"
    assumptions = brief["assumptions"]
    assert isinstance(assumptions, list) and assumptions

    ids = {entry["id"] for entry in assumptions}
    assert EXPECTED_ASSUMPTION_IDS <= ids

    for entry in assumptions:
        assert entry["basis"] == "synthetic-demo-assumption"
        assert entry["statement"].strip()
        # Every assumption must point back at what it drives in the pack.
        assert entry.get("design_relevance"), entry["id"]


def test_assumptions_are_separated_from_facts_and_uncertainties() -> None:
    brief = _brief()

    assumption_ids = {entry["id"] for entry in brief["assumptions"]}
    fact_ids = {entry["id"] for entry in brief["facts"]}
    uncertainty_ids = {entry["id"] for entry in brief["uncertainties"]}

    assert assumption_ids.isdisjoint(fact_ids)
    assert assumption_ids.isdisjoint(uncertainty_ids)


def test_assumptions_enumerate_the_wired_thresholds_and_scale() -> None:
    brief = _brief()
    text = " ".join(entry["statement"] for entry in brief["assumptions"])

    # Governance thresholds actually enforced in verticals/fashion/world.py.
    assert "10,000" in text or "10000" in text  # transfer value approval gate
    assert "50" in text  # transfer quantity approval gate
    assert "0.7" in text  # demand-confidence floor
    assert "0.5" in text  # fairness-score floor
    # Transfer cost vs recovered margin comparison.
    assert "margin" in text.lower() and "cost" in text.lower()
    # Protected safety-stock buffer (conditional HITL, not a hard reject).
    assert "safety stock" in text.lower() or "safety-stock" in text.lower()
    # Actor-world scale counts.
    for count in ("8", "2", "12", "24", "192", "300", "14"):
        assert count in text
