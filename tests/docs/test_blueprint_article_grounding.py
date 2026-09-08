"""
RED phase: cross-language manifest inventory checks.
Reads every verticals/*/manifest.py, extracts display_name="..." literals,
and asserts all names appear in web/blueprint/src/sections/Verticals.tsx.
These checks are here (Python) because the TypeScript source tests cannot
robustly read Python manifests.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERTICALS_DIR = REPO_ROOT / "verticals"
VERTICALS_TSX = REPO_ROOT / "web" / "blueprint" / "src" / "sections" / "Verticals.tsx"

EXPECTED_DISPLAY_NAMES = [
    "Agency",
    "Telco",
    "Fashion Retail",
    "Travel",
    "Synthetic Airline Operations",
    "Hospitality",
    "Electronics Retail",
]

EXPECTED_MANIFEST_COUNT = 7


def _extract_display_name(manifest_path: Path) -> str:
    """Extract the literal display_name="..." value from a manifest.py file."""
    text = manifest_path.read_text(encoding="utf-8")
    match = re.search(r'display_name\s*=\s*"([^"]+)"', text)
    if not match:
        raise AssertionError(
            f"No literal display_name=\"...\" found in {manifest_path}. "
            "Add display_name=\"<Name>\" to this manifest."
        )
    return match.group(1)


def _get_all_manifests() -> list[Path]:
    return sorted(VERTICALS_DIR.glob("*/manifest.py"))


def test_manifest_count() -> None:
    """There are currently exactly 7 vertical manifest files."""
    manifests = _get_all_manifests()
    assert len(manifests) == EXPECTED_MANIFEST_COUNT, (
        f"Expected {EXPECTED_MANIFEST_COUNT} manifest files, "
        f"found {len(manifests)}: {[str(m) for m in manifests]}"
    )


def test_all_display_names_in_verticals_tsx() -> None:
    """Every manifest display_name appears in Verticals.tsx."""
    assert VERTICALS_TSX.exists(), (
        f"Verticals.tsx does not exist at {VERTICALS_TSX}. "
        "Create web/blueprint/src/sections/Verticals.tsx."
    )
    tsx_content = VERTICALS_TSX.read_text(encoding="utf-8")

    manifests = _get_all_manifests()
    assert manifests, "No manifest.py files found under verticals/"

    missing: list[str] = []
    for manifest in manifests:
        name = _extract_display_name(manifest)
        if name not in tsx_content:
            missing.append(f"{name!r} (from {manifest.relative_to(REPO_ROOT)})")

    assert not missing, (
        f"The following manifest display names are missing from Verticals.tsx:\n"
        + "\n".join(f"  - {m}" for m in missing)
    )


def test_verticals_tsx_expected_names() -> None:
    """Verticals.tsx contains the full expected set of display names."""
    assert VERTICALS_TSX.exists(), (
        f"Verticals.tsx does not exist at {VERTICALS_TSX}."
    )
    tsx_content = VERTICALS_TSX.read_text(encoding="utf-8")

    missing = [n for n in EXPECTED_DISPLAY_NAMES if n not in tsx_content]
    assert not missing, (
        f"Verticals.tsx is missing expected display names: {missing}"
    )


def test_verticals_tsx_pack_presence_not_readiness() -> None:
    """Verticals.tsx says pack presence is not readiness."""
    assert VERTICALS_TSX.exists(), f"Verticals.tsx does not exist at {VERTICALS_TSX}."
    tsx_content = VERTICALS_TSX.read_text(encoding="utf-8")
    assert re.search(r"presence.{0,30}not readiness|not readiness", tsx_content, re.IGNORECASE), (
        "Verticals.tsx must state that pack presence is not readiness."
    )


def test_verticals_tsx_telco_canonical_proof() -> None:
    """Verticals.tsx says only Telco is the canonical proof reference."""
    assert VERTICALS_TSX.exists(), f"Verticals.tsx does not exist at {VERTICALS_TSX}."
    tsx_content = VERTICALS_TSX.read_text(encoding="utf-8")
    assert re.search(
        r"telco.{0,80}canonical proof|canonical proof.{0,80}telco",
        tsx_content,
        re.IGNORECASE,
    ), "Verticals.tsx must name Telco as the canonical proof reference."
