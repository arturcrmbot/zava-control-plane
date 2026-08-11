"""Tests for tools/public_replay_manifest.py."""
from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from tools.public_replay_manifest import build_manifest, verify_manifest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tape(path: Path, *, tape_id: str = "tape_test", recorded_at: str = "2026-08-10T09:00:00+00:00") -> None:
    meta = json.dumps(
        {
            "tape_id": tape_id,
            "recorded_at": recorded_at,
            "duration_s": 60,
            "version": 1,
            "app_sha": "abc1234",
        },
    ).encode()
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("./meta.json")
        info.size = len(meta)
        archive.addfile(info, io.BytesIO(meta))


def _write_proof(path: Path, source_commit: str) -> None:
    path.write_text(
        json.dumps(
            {
                "source_commit": source_commit,
                "live_result": "PASS",
                "replay_result": "PASS",
                "seller_review": "PENDING",
                "browserErrors": [],
            },
        ),
    )


def _write_seller_review(path: Path, status: str = "PASS", *, machine_may_approve: bool = False) -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "owner": "operator",
                "machine_may_approve": machine_may_approve,
                "questions": [
                    {"id": 1, "question": "Story coherent?", "answer": True},
                ],
            },
        ),
    )


# ---------------------------------------------------------------------------
# Happy-path: build
# ---------------------------------------------------------------------------

def test_build_manifest_binds_tape_proof_and_story(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)

    manifest = build_manifest(tape, proof, seller_review, "a" * 40)

    assert manifest["schema_version"] == 1
    assert manifest["source_commit"] == "a" * 40
    assert len(manifest["tape_sha256"]) == 64
    assert len(manifest["proof_manifest_sha256"]) == 64
    assert len(manifest["seller_review_sha256"]) == 64
    assert manifest["recorded_at"] == "2026-08-10T09:00:00+00:00"
    assert manifest["story_contract"].endswith(
        "2026-08-10-zava-constellation-story-design.md",
    )
    assert manifest["tape_id"] == "tape_test"


# ---------------------------------------------------------------------------
# Seller-review failures
# ---------------------------------------------------------------------------

def test_build_manifest_refuses_pending_seller_review(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review, status="PENDING")

    with pytest.raises(ValueError, match="seller_review must be PASS"):
        build_manifest(tape, proof, seller_review, "a" * 40)


def test_build_manifest_refuses_machine_may_approve_true(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review, machine_may_approve=True)

    with pytest.raises(ValueError, match="machine_may_approve"):
        build_manifest(tape, proof, seller_review, "a" * 40)


def test_build_manifest_refuses_non_boolean_answer(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    seller_review.write_text(
        json.dumps(
            {
                "status": "PASS",
                "owner": "operator",
                "machine_may_approve": False,
                "questions": [
                    {"id": 1, "question": "Story coherent?", "answer": "yes"},
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="explicitly true"):
        build_manifest(tape, proof, seller_review, "a" * 40)


def test_build_manifest_refuses_false_answer(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    seller_review.write_text(
        json.dumps(
            {
                "status": "PASS",
                "owner": "operator",
                "machine_may_approve": False,
                "questions": [
                    {"id": 1, "question": "Story coherent?", "answer": False},
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="explicitly true"):
        build_manifest(tape, proof, seller_review, "a" * 40)


# ---------------------------------------------------------------------------
# Proof failures
# ---------------------------------------------------------------------------

def test_build_manifest_refuses_source_mismatch(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)

    with pytest.raises(ValueError, match="source_commit"):
        build_manifest(tape, proof, seller_review, "b" * 40)


# ---------------------------------------------------------------------------
# Verify drift detection
# ---------------------------------------------------------------------------

def test_verify_manifest_detects_tape_drift(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    manifest_path = tmp_path / "public-replay.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)
    manifest_path.write_text(
        json.dumps(build_manifest(tape, proof, seller_review, "a" * 40)),
    )

    with tape.open("ab") as stream:
        stream.write(b"drift")

    with pytest.raises(ValueError, match="tape sha256 mismatch"):
        verify_manifest(tape, proof, seller_review, manifest_path, "a" * 40)


def test_verify_manifest_detects_proof_drift(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    manifest_path = tmp_path / "public-replay.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)
    manifest_path.write_text(
        json.dumps(build_manifest(tape, proof, seller_review, "a" * 40)),
    )

    # Now change proof after manifest was written
    _write_proof(proof, "a" * 40)  # rewrite with whitespace difference
    proof.write_bytes(proof.read_bytes() + b" ")

    with pytest.raises(ValueError, match="proof manifest sha256 mismatch"):
        verify_manifest(tape, proof, seller_review, manifest_path, "a" * 40)


def test_verify_manifest_detects_seller_review_drift(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    manifest_path = tmp_path / "public-replay.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)
    manifest_path.write_text(
        json.dumps(build_manifest(tape, proof, seller_review, "a" * 40)),
    )

    seller_review.write_bytes(seller_review.read_bytes() + b" ")

    with pytest.raises(ValueError, match="seller review sha256 mismatch"):
        verify_manifest(tape, proof, seller_review, manifest_path, "a" * 40)


# ---------------------------------------------------------------------------
# Tape meta validation
# ---------------------------------------------------------------------------

def test_build_manifest_refuses_tape_missing_tape_id(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    meta = json.dumps({"recorded_at": "2026-01-01T00:00:00Z"}).encode()
    with tarfile.open(tape, "w:gz") as archive:
        info = tarfile.TarInfo("./meta.json")
        info.size = len(meta)
        archive.addfile(info, io.BytesIO(meta))
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)

    with pytest.raises(ValueError, match="tape_id"):
        build_manifest(tape, proof, seller_review, "a" * 40)


def test_build_manifest_refuses_tape_missing_meta_json(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    payload = b"content"
    with tarfile.open(tape, "w:gz") as archive:
        info = tarfile.TarInfo("./events.ndjson")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)

    with pytest.raises(ValueError, match="meta.json"):
        build_manifest(tape, proof, seller_review, "a" * 40)


def test_build_manifest_accepts_meta_json_without_leading_dot(tmp_path: Path) -> None:
    """Tape members named 'meta.json' (no ./ prefix) are also accepted."""
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    meta = json.dumps({"tape_id": "t1", "recorded_at": "2026-08-10T00:00:00Z"}).encode()
    with tarfile.open(tape, "w:gz") as archive:
        info = tarfile.TarInfo("meta.json")  # no "./" prefix
        info.size = len(meta)
        archive.addfile(info, io.BytesIO(meta))
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)

    manifest = build_manifest(tape, proof, seller_review, "a" * 40)
    assert manifest["tape_id"] == "t1"


# ---------------------------------------------------------------------------
# Tape member type validation (symlink / hardlink / other non-regular)
# ---------------------------------------------------------------------------

def test_tape_meta_refuses_symlink_member(tmp_path: Path) -> None:
    """A meta.json tar member that is a symlink must be rejected, not extracted."""
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    with tarfile.open(tape, "w:gz") as archive:
        info = tarfile.TarInfo("./meta.json")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        info.size = 0
        archive.addfile(info, io.BytesIO(b""))
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)

    with pytest.raises(ValueError, match="not a regular file"):
        build_manifest(tape, proof, seller_review, "a" * 40)


def test_tape_meta_refuses_hardlink_member(tmp_path: Path) -> None:
    """A meta.json tar member that is a hard-link must be rejected."""
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    with tarfile.open(tape, "w:gz") as archive:
        info = tarfile.TarInfo("./meta.json")
        info.type = tarfile.LNKTYPE
        info.linkname = "other_file"
        info.size = 0
        archive.addfile(info, io.BytesIO(b""))
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)

    with pytest.raises(ValueError, match="not a regular file"):
        build_manifest(tape, proof, seller_review, "a" * 40)


# ---------------------------------------------------------------------------
# Verify: stored schema_version / tape_id / recorded_at tampering
# ---------------------------------------------------------------------------

def test_verify_manifest_detects_schema_version_tampering(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    manifest_path = tmp_path / "public-replay.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)
    stored = build_manifest(tape, proof, seller_review, "a" * 40)
    stored["schema_version"] = 99  # tamper
    manifest_path.write_text(json.dumps(stored))

    with pytest.raises(ValueError, match="schema_version mismatch"):
        verify_manifest(tape, proof, seller_review, manifest_path, "a" * 40)


def test_verify_manifest_detects_tape_id_tampering(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    manifest_path = tmp_path / "public-replay.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)
    stored = build_manifest(tape, proof, seller_review, "a" * 40)
    stored["tape_id"] = "tampered_tape_id"  # tamper
    manifest_path.write_text(json.dumps(stored))

    with pytest.raises(ValueError, match="tape_id mismatch"):
        verify_manifest(tape, proof, seller_review, manifest_path, "a" * 40)


def test_verify_manifest_detects_recorded_at_tampering(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    manifest_path = tmp_path / "public-replay.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)
    stored = build_manifest(tape, proof, seller_review, "a" * 40)
    stored["recorded_at"] = "1970-01-01T00:00:00Z"  # tamper
    manifest_path.write_text(json.dumps(stored))

    with pytest.raises(ValueError, match="recorded_at mismatch"):
        verify_manifest(tape, proof, seller_review, manifest_path, "a" * 40)
