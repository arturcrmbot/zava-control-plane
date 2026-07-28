"""Task 1: Verify the hospitality pack inventory from static YAML/JSON assets."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
ORG_BRIEF = ROOT / "verticals" / "hospitality" / "org-brief.yaml"
MANIFEST = ROOT / "verticals" / "hospitality" / "generation-manifest.json"
UI_JSON = ROOT / "verticals" / "hospitality" / "ui.json"

EXPECTED_WORKFLOW_IDS = {
    "hotel-operations-recovery",
    "room-readiness-coordination",
    "asset-maintenance-response",
    "guest-service-recovery",
    "occupancy-pressure-response",
    "workforce-demand-balancing",
    "food-and-beverage-readiness",
    "energy-anomaly-response",
}


def test_org_brief_exists_and_declares_workflow_inventory() -> None:
    assert ORG_BRIEF.exists(), f"org-brief.yaml not found at {ORG_BRIEF}"
    brief = yaml.safe_load(ORG_BRIEF.read_text(encoding="utf-8"))
    assert "workflow_inventory" in brief, "org-brief.yaml must contain workflow_inventory"
    declared = set(brief["workflow_inventory"])
    assert declared == EXPECTED_WORKFLOW_IDS, (
        f"workflow_inventory mismatch.\n  missing: {EXPECTED_WORKFLOW_IDS - declared}\n"
        f"  extra: {declared - EXPECTED_WORKFLOW_IDS}"
    )


def test_org_brief_slug_is_hospitality() -> None:
    assert ORG_BRIEF.exists(), f"org-brief.yaml not found at {ORG_BRIEF}"
    brief = yaml.safe_load(ORG_BRIEF.read_text(encoding="utf-8"))
    assert brief.get("slug") == "hospitality", (
        f"org-brief.yaml slug must be 'hospitality', got {brief.get('slug')!r}"
    )


def test_generation_manifest_exists_and_vertical_is_hospitality() -> None:
    assert MANIFEST.exists(), f"generation-manifest.json not found at {MANIFEST}"
    ledger = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert ledger.get("vertical") == "hospitality", (
        f"generation-manifest.json vertical must be 'hospitality', got {ledger.get('vertical')!r}"
    )


def test_generation_manifest_schema_version_is_1() -> None:
    assert MANIFEST.exists(), f"generation-manifest.json not found at {MANIFEST}"
    ledger = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert ledger.get("schema_version") == 1, (
        f"schema_version must be 1, got {ledger.get('schema_version')!r}"
    )


def test_generation_manifest_all_ownership_values_start_with_bespoke() -> None:
    assert MANIFEST.exists(), f"generation-manifest.json not found at {MANIFEST}"
    ledger = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = ledger.get("records", [])
    assert records, "generation-manifest.json must contain at least one record"
    bad = [
        r for r in records
        if not str(r.get("ownership", "")).startswith("bespoke")
    ]
    assert not bad, (
        f"All ownership values must start with 'bespoke'. Violations: {bad}"
    )


def test_ui_json_lenses_are_subset_of_known_lenses() -> None:
    from api.shared.kernel_assets import KNOWN_LENSES

    assert UI_JSON.exists(), f"ui.json not found at {UI_JSON}"
    ui = json.loads(UI_JSON.read_text(encoding="utf-8"))
    lenses = set(ui.get("lenses", []))
    unknown = lenses - KNOWN_LENSES
    assert not unknown, (
        f"ui.json contains lenses not in KNOWN_LENSES: {unknown}\n"
        f"  KNOWN_LENSES={sorted(KNOWN_LENSES)}"
    )


def test_ui_json_capabilities_are_subset_of_known_capabilities() -> None:
    from api.shared.kernel_assets import KNOWN_CAPABILITIES

    assert UI_JSON.exists(), f"ui.json not found at {UI_JSON}"
    ui = json.loads(UI_JSON.read_text(encoding="utf-8"))
    capabilities = set(ui.get("capabilities", []))
    unknown = capabilities - KNOWN_CAPABILITIES
    assert not unknown, (
        f"ui.json contains capabilities not in KNOWN_CAPABILITIES: {unknown}\n"
        f"  KNOWN_CAPABILITIES={sorted(KNOWN_CAPABILITIES)}"
    )
