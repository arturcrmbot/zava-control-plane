"""Public replay provenance manifest tool.

Binds a replay tape, proof/manifest.json, and proof/seller-review.json to a
specific source commit so deployments are traceable and tamper-evident.

CLI usage:
  python tools/public_replay_manifest.py write --source-commit <sha>
  python tools/public_replay_manifest.py verify --source-commit <sha>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

STORY_CONTRACT = (
    "docs/superpowers/specs/"
    "2026-08-10-zava-constellation-story-design.md"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tape_meta(path: Path) -> dict[str, Any]:
    """Read meta.json from a tape tar.gz without extracting to the filesystem."""
    with tarfile.open(path, "r:gz") as archive:
        # Accept both ./meta.json and meta.json as member names.
        candidate_names = ("./meta.json", "meta.json")
        member = None
        for name in candidate_names:
            try:
                member = archive.getmember(name)
                break
            except KeyError:
                continue
        if member is None:
            raise ValueError("tape does not contain meta.json")
        # Reject anything that is not a plain regular file: symlinks, hard-links,
        # block/char devices, fifos, etc.  tarfile.REGTYPE == b'0', AREGTYPE == b'\0'.
        if not member.isfile():
            raise ValueError(
                f"tape meta.json member is not a regular file "
                f"(type={member.type!r}); symlinks and other non-regular "
                "entries are not permitted"
            )
        stream = archive.extractfile(member)
        if stream is None:
            raise ValueError("tape meta.json is unreadable")
        data = json.loads(stream.read())
    tape_id = data.get("tape_id")
    recorded_at = data.get("recorded_at")
    if not tape_id or not isinstance(tape_id, str):
        raise ValueError("tape meta.json missing non-empty tape_id")
    if not recorded_at or not isinstance(recorded_at, str):
        raise ValueError("tape meta.json missing non-empty recorded_at")
    return data


def _validate_proof(path: Path, source_commit: str) -> dict[str, Any]:
    proof = json.loads(path.read_text(encoding="utf-8"))
    sc = proof.get("source_commit")
    if not isinstance(sc, str) or not sc:
        raise ValueError("proof source_commit is missing or empty")
    if sc != source_commit:
        raise ValueError(
            f"proof source_commit does not match HEAD: "
            f"expected {source_commit!r}, got {sc!r}"
        )
    if proof.get("live_result") != "PASS":
        raise ValueError("live_result must be PASS")
    if proof.get("replay_result") != "PASS":
        raise ValueError("replay_result must be PASS")
    if proof.get("browserErrors") != []:
        raise ValueError("browserErrors must be empty list")
    return proof


def _validate_seller_review(path: Path) -> dict[str, Any]:
    review = json.loads(path.read_text(encoding="utf-8"))
    if review.get("status") != "PASS":
        raise ValueError("seller_review must be PASS")
    owner = review.get("owner")
    if not owner or not isinstance(owner, str):
        raise ValueError("seller_review owner must be non-empty")
    if review.get("machine_may_approve") is not False:
        raise ValueError("seller review machine_may_approve must be false — must remain operator-owned")
    questions = review.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("seller review questions must be a non-empty list")
    for item in questions:
        answer = item.get("answer")
        if answer is not True:
            raise ValueError(
                f"all seller review answers must be explicitly true (bool); "
                f"got {answer!r} for question id={item.get('id')!r}"
            )
    return review


def build_manifest(
    tape_path: Path,
    proof_path: Path,
    seller_review_path: Path,
    source_commit: str,
) -> dict[str, Any]:
    """Validate all inputs and return the provenance manifest dict."""
    _validate_proof(proof_path, source_commit)
    _validate_seller_review(seller_review_path)
    meta = _tape_meta(tape_path)
    return {
        "schema_version": 1,
        "source_commit": source_commit,
        "story_contract": STORY_CONTRACT,
        "tape_id": meta["tape_id"],
        "recorded_at": meta["recorded_at"],
        "tape_sha256": _sha256(tape_path),
        "proof_manifest_sha256": _sha256(proof_path),
        "seller_review_sha256": _sha256(seller_review_path),
    }


def verify_manifest(
    tape_path: Path,
    proof_path: Path,
    seller_review_path: Path,
    manifest_path: Path,
    source_commit: str,
) -> None:
    """Re-derive the manifest and compare every field/digest against the stored one."""
    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = build_manifest(tape_path, proof_path, seller_review_path, source_commit)

    if stored.get("source_commit") != actual["source_commit"]:
        raise ValueError(
            f"source_commit mismatch: stored {stored.get('source_commit')!r}, "
            f"current {actual['source_commit']!r}"
        )
    if stored.get("schema_version") != actual["schema_version"]:
        raise ValueError(
            f"schema_version mismatch: stored {stored.get('schema_version')!r}, "
            f"current {actual['schema_version']!r}"
        )
    if stored.get("tape_id") != actual["tape_id"]:
        raise ValueError(
            f"tape_id mismatch: stored {stored.get('tape_id')!r}, "
            f"current {actual['tape_id']!r}"
        )
    if stored.get("recorded_at") != actual["recorded_at"]:
        raise ValueError(
            f"recorded_at mismatch: stored {stored.get('recorded_at')!r}, "
            f"current {actual['recorded_at']!r}"
        )
    if stored.get("tape_sha256") != actual["tape_sha256"]:
        raise ValueError(
            f"tape sha256 mismatch: stored {stored.get('tape_sha256')!r}, "
            f"current {actual['tape_sha256']!r}"
        )
    if stored.get("proof_manifest_sha256") != actual["proof_manifest_sha256"]:
        raise ValueError(
            f"proof manifest sha256 mismatch: stored {stored.get('proof_manifest_sha256')!r}, "
            f"current {actual['proof_manifest_sha256']!r}"
        )
    if stored.get("seller_review_sha256") != actual["seller_review_sha256"]:
        raise ValueError(
            f"seller review sha256 mismatch: stored {stored.get('seller_review_sha256')!r}, "
            f"current {actual['seller_review_sha256']!r}"
        )
    if stored.get("story_contract") != STORY_CONTRACT:
        raise ValueError(
            f"story contract mismatch: stored {stored.get('story_contract')!r}, "
            f"expected {STORY_CONTRACT!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Public replay provenance manifest tool."
    )
    parser.add_argument("command", choices=("write", "verify"))
    parser.add_argument("--tape", type=Path, default=Path("tapes/demo.tar.gz"))
    parser.add_argument("--proof", type=Path, default=Path("proof/manifest.json"))
    parser.add_argument(
        "--seller-review",
        type=Path,
        default=Path("proof/seller-review.json"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("proof/public-replay.json"),
    )
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()

    if args.command == "write":
        payload = build_manifest(
            args.tape,
            args.proof,
            args.seller_review,
            args.source_commit,
        )
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Manifest written to {args.manifest}")
    else:
        verify_manifest(
            args.tape,
            args.proof,
            args.seller_review,
            args.manifest,
            args.source_commit,
        )
        print("Manifest verified OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
