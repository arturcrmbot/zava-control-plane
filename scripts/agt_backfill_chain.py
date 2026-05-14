#!/usr/bin/env python3
"""Backfill prev_hash / entry_hash on historical audit ledger blobs.

Per plan/feature-agent-governance-toolkit-1.md TASK-033 of Phase 4.

Walks every workflow blob under
``azurite-data/__blobstorage__/audit-ledger/`` (or any path passed via
``--root``) and rewrites entries so each one carries the per-workflow
hash chain that ``api/server/services/audit_logger.py`` started writing
in Phase 4. After this script runs, ``GET /api/governance/verify/{wid}``
returns ``chain_intact=true`` for every historical workflow.

Idempotent: re-running is a no-op. The script reads each entry, only
recomputes prev_hash / entry_hash when at least one is missing or
inconsistent, and writes back only when something actually changed.

Safety:
- Reads each blob, walks entries in order, computes the hash chain
  from genesis, writes the result to a sibling ``.bak`` file FIRST,
  then atomic-renames over the original. A crash mid-run leaves the
  original intact.
- Pure local-filesystem walk by default (Azurite blob layout). Pointed
  at a different ``--root`` it works on any directory of ``*.jsonl``
  files following the ``{workflow_id}.jsonl`` convention.

Usage:
  python scripts/agt_backfill_chain.py
  python scripts/agt_backfill_chain.py --root /path/to/blobs --dry-run

Documented in docs/DEVELOPMENT.md (Phase 4 section).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make the script runnable from anywhere — re-use the canonical
# hashing helper from the AuditLogger so the chain is computed
# bit-for-bit the same way.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from api.server.services.audit_logger import (  # noqa: E402
    _GENESIS_HASH,
    _canonical_entry_hash,
)


_DEFAULT_ROOT = (
    _REPO_ROOT / "azurite-data" / "__blobstorage__" / "audit-ledger"
)


def _iter_blobs(root: Path) -> list[Path]:
    """Return all candidate ``*.jsonl`` audit blobs under ``root``.

    Matches both top-level files and nested ones (Azurite stores blobs
    in a content-hash-prefixed subdirectory tree, so glob recursively).
    """
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.jsonl") if p.is_file())


def _backfill_blob(path: Path, dry_run: bool = False) -> tuple[int, int]:
    """Rewrite ``path`` so every entry carries a valid hash chain.

    Returns ``(entries, changes)``. ``changes`` is the number of
    entries whose ``prev_hash`` or ``entry_hash`` had to be
    written / corrected.
    """
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    entries: list[dict] = []
    for ln, text in enumerate(lines, 1):
        text = text.strip()
        if not text:
            continue
        try:
            entry = json.loads(text)
        except json.JSONDecodeError as ex:
            raise ValueError(f"{path}:{ln} not valid JSON: {ex}") from ex
        if not isinstance(entry, dict):
            raise ValueError(f"{path}:{ln} not a JSON object: {entry!r}")
        entries.append(entry)

    changes = 0
    expected_prev = _GENESIS_HASH
    for entry in entries:
        # Strip prior entry_hash before recomputing — the canonical hash
        # function already excludes it, but explicit is better than
        # implicit and makes the diff readable.
        prior_prev = entry.get("prev_hash")
        prior_hash = entry.get("entry_hash")

        entry["prev_hash"] = expected_prev
        recomputed = _canonical_entry_hash(entry)
        entry["entry_hash"] = recomputed

        if prior_prev != expected_prev or prior_hash != recomputed:
            changes += 1
        expected_prev = recomputed

    if changes == 0:
        return (len(entries), 0)

    if dry_run:
        return (len(entries), changes)

    # Atomic write via .bak rename.
    bak = path.with_suffix(path.suffix + ".bak")
    payload = "".join(
        json.dumps(e, ensure_ascii=False, default=str) + "\n" for e in entries
    )
    bak.write_text(payload, encoding="utf-8")
    os.replace(bak, path)
    return (len(entries), changes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=_DEFAULT_ROOT,
        help=(
            "Directory containing audit ledger *.jsonl blobs. "
            f"Default: {_DEFAULT_ROOT.relative_to(_REPO_ROOT)}"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Walk + report without writing.",
    )
    args = parser.parse_args(argv)

    blobs = _iter_blobs(args.root)
    if not blobs:
        print(f"agt_backfill: no *.jsonl blobs found under {args.root}")
        return 0

    total_entries = 0
    total_changes = 0
    rewritten = 0
    for blob in blobs:
        entries, changes = _backfill_blob(blob, dry_run=args.dry_run)
        total_entries += entries
        total_changes += changes
        if changes:
            rewritten += 1
            print(
                f"agt_backfill: {blob.relative_to(args.root)} — "
                f"{entries} entries, {changes} chained "
                f"({'dry-run' if args.dry_run else 'rewritten'})"
            )
        else:
            print(
                f"agt_backfill: {blob.relative_to(args.root)} — "
                f"{entries} entries, already chained"
            )

    summary = (
        f"agt_backfill: {len(blobs)} blob(s), {total_entries} entries, "
        f"{total_changes} chained across {rewritten} file(s)"
    )
    if args.dry_run:
        summary += " (dry-run; no writes)"
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
