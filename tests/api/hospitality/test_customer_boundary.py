"""Task 1: Verify no forbidden customer-identifying terms appear in hospitality assets."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOSPITALITY_PACK = ROOT / "verticals" / "hospitality"
HOSPITALITY_TESTS = ROOT / "tests" / "api" / "hospitality"

# Forbidden case-insensitive terms — customer identity must never appear
FORBIDDEN = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bwhitbread\b",
        r"\bpremier\s+inn\b",
        r"\bcosta\b",
        r"\bbeefeater\b",
        r"\bbrewers\s+fayre\b",
    ]
]

SCAN_SUFFIXES = {".py", ".json", ".yaml", ".yml", ".md"}


def _scan_dir(
    directory: Path,
    exclude_paths: frozenset[Path] | None = None,
) -> list[tuple[Path, str, str]]:
    """Return (file, pattern, matched_text) for each violation found."""
    violations: list[tuple[Path, str, str]] = []
    if not directory.exists():
        return violations
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in SCAN_SUFFIXES:
            continue
        if exclude_paths and path in exclude_paths:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern in FORBIDDEN:
            for match in pattern.finditer(text):
                violations.append((path, pattern.pattern, match.group()))
    return violations


def test_pack_assets_contain_no_forbidden_customer_terms() -> None:
    violations = _scan_dir(HOSPITALITY_PACK)
    assert not violations, (
        "Forbidden customer-identifying terms found in pack assets:\n"
        + "\n".join(f"  {p}: pattern={pat!r} match={m!r}" for p, pat, m in violations)
    )


def test_test_assets_contain_no_forbidden_customer_terms() -> None:
    # Exclude this file: its FORBIDDEN list embeds the literal terms as regex
    # pattern strings, which would self-match and produce false positives.
    violations = _scan_dir(HOSPITALITY_TESTS, exclude_paths=frozenset({Path(__file__).resolve()}))
    assert not violations, (
        "Forbidden customer-identifying terms found in test assets:\n"
        + "\n".join(f"  {p}: pattern={pat!r} match={m!r}" for p, pat, m in violations)
    )


def test_scanner_detects_forbidden_term_in_tmp_file(tmp_path: Path) -> None:
    """Positive-detection proof: scanner finds a forbidden term in a probe file.

    Skipping the scanner source does not weaken detection — the real scanner
    helper is exercised against a synthetic file that contains a known term.
    """
    probe = tmp_path / "probe.py"
    probe.write_text("# property: whitbread hotels\n", encoding="utf-8")

    violations = _scan_dir(tmp_path)
    assert violations, "Scanner must detect the forbidden term in the probe file"
    matched_paths = {v[0] for v in violations}
    assert probe in matched_paths, (
        f"Expected {probe} in violations, got: {matched_paths}"
    )
