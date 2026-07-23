"""Parity guard: the committed `verticals/travel/` generated outputs must
be byte-identical to what `verticals.travel.generator` produces today.

This closes a quality gap in Task 3's coverage: the existing generator
contract tests (`test_generate_travel_vertical.py`) only ever generate
into `tmp_path` and check *that* output's shape/content -- nothing
committed anchors the real, repo-root `verticals/travel/` files (which a
human or another tool could hand-edit after generation) back to the
generator that is supposed to own them. This module is that anchor.

It also proves the comparison itself is not vacuous: `_diverging_paths`
is exercised a second time against a deliberately corrupted *copy* of the
generated output in a throwaway temp root (never the real committed
files) and must report exactly the one path that was corrupted.
"""
from __future__ import annotations

import json
from pathlib import Path

from verticals.travel.generator.render import generate

# tests/tools/test_travel_generated_output_parity.py -> repo root is two parents up.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_PATH = _REPO_ROOT / "verticals" / "travel" / "generation-manifest.json"


def _manifest_asset_paths(manifest: dict) -> list[str]:
    """Every repo-root-relative path a generation manifest is responsible
    for: every listed record's `path`, plus the manifest file itself
    (which tracks every generated asset but, per the generation-manifest
    contract, is not itself a tracked record).
    """
    paths = [record["path"] for record in manifest["records"]]
    manifest_relative = _MANIFEST_PATH.relative_to(_REPO_ROOT).as_posix()
    paths.append(manifest_relative)
    return paths


def _diverging_paths(root_a: Path, root_b: Path, relative_paths: list[str]) -> list[str]:
    """Byte-compare every `relative_paths` entry between two roots.

    Returns the sorted list of paths whose bytes differ, including any
    path present under one root but missing (or unreadable as a file)
    under the other -- so a deleted or renamed generated asset is caught
    exactly like a corrupted one.
    """
    diverging: list[str] = []
    for relative_path in relative_paths:
        path_a = root_a / relative_path
        path_b = root_b / relative_path
        bytes_a = path_a.read_bytes() if path_a.is_file() else None
        bytes_b = path_b.read_bytes() if path_b.is_file() else None
        if bytes_a != bytes_b:
            diverging.append(relative_path)
    return sorted(diverging)


def test_generated_output_matches_committed_repo_root_bytes(tmp_path: Path) -> None:
    """Regenerating into a fresh tmp_path must byte-match every
    manifest-listed asset plus generation-manifest.json as they actually
    sit at the repo root -- proving nothing was hand-edited after the
    last regeneration.
    """
    manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    relative_paths = _manifest_asset_paths(manifest)
    assert relative_paths, "expected the manifest to list at least one asset"

    generate(target_root=tmp_path)

    diverging = _diverging_paths(tmp_path, _REPO_ROOT, relative_paths)
    assert diverging == [], (
        f"generated output at the repo root has drifted from what the generator "
        f"produces: {diverging}"
    )


def test_parity_guard_detects_a_deliberately_corrupted_generated_asset(tmp_path: Path) -> None:
    """Prove the comparison above actually detects drift and reports the
    exact divergent path: generate into two independent temporary roots,
    corrupt one copied generated asset in the second, and confirm
    `_diverging_paths` reports precisely that one path -- without ever
    touching the real committed generated files.
    """
    manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    relative_paths = _manifest_asset_paths(manifest)

    clean_root = tmp_path / "clean"
    corrupted_root = tmp_path / "corrupted"
    generate(target_root=clean_root)
    generate(target_root=corrupted_root)

    # Sanity: the two independently generated roots start out identical.
    assert _diverging_paths(clean_root, corrupted_root, relative_paths) == []

    corrupted_relative_path = "verticals/travel/worlds/scenario.py"
    assert corrupted_relative_path in relative_paths
    corrupted_file = corrupted_root / corrupted_relative_path
    corrupted_file.write_bytes(corrupted_file.read_bytes() + b"\n# deliberately corrupted\n")

    diverging = _diverging_paths(clean_root, corrupted_root, relative_paths)
    assert diverging == [corrupted_relative_path]
