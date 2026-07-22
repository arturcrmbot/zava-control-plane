#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACK_MANIFEST = ROOT / "verticals" / "fashion" / "generation-manifest.json"
SELLER_QUESTIONS = (
    "Is the industry and operating setting recognisable?",
    "Is the business event understandable without narration?",
    "Is it visible why the process started?",
    "Are the agent and human decisions inspectable?",
    "Is the business and Knowledge-graph outcome visible?",
)


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required proof artifact is missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"proof artifact must contain an object: {path}")
    return data


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _is_clean() -> bool:
    return not subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _seller_review(path: Path) -> None:
    payload = {
        "status": "PENDING",
        "owner": "operator",
        "machine_may_approve": False,
        "questions": [
            {"id": index, "question": question, "answer": None}
            for index, question in enumerate(SELLER_QUESTIONS, start=1)
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_manifest(
    proof_dir: Path,
    *,
    dirty_development: bool,
) -> tuple[dict[str, Any], bool]:
    live = _load(proof_dir / "live-summary.json")
    replay = _load(proof_dir / "replay-summary.json")
    observed_head = _head()
    clean = _is_clean()
    if not dirty_development and not clean:
        raise ValueError(
            "clean-source guard failed; use --dirty-development for a "
            "non-attributed development proof"
        )

    live_result = str(live.get("result") or "FAIL")
    replay_result = str(replay.get("result") or "FAIL")
    substrate_result = (
        "PASS"
        if live.get("substrate_result") == "PASS"
        and replay.get("substrate_result") == "PASS"
        and replay_result == "PASS"
        else "FAIL"
    )
    demo_result = (
        "PASS"
        if live.get("demo_result") == "PASS"
        and live_result == "PASS"
        and replay_result == "PASS"
        else "FAIL"
    )
    if substrate_result != "PASS":
        overall = "substrate-incomplete / demo-incomplete"
    elif demo_result != "PASS":
        overall = "substrate-complete / demo-incomplete"
    else:
        overall = (
            "substrate-complete / demo-complete / seller-review-pending"
        )
    browser_errors = [
        *list(live.get("browserErrors") or []),
        *list(replay.get("browserErrors") or []),
    ]
    attributed = clean and not dirty_development
    manifest = {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vertical": "fashion",
        "fingerprint": "fashion:2",
        "source_commit": observed_head if attributed else None,
        "source_commit_observed": observed_head,
        "source_attribution": (
            "CLEAN_COMMIT" if attributed else "DIRTY_DEVELOPMENT"
        ),
        "permanent_result": "PASS" if attributed else "PENDING",
        "live_result": live_result,
        "replay_result": replay_result,
        "substrate_result": substrate_result,
        "demo_result": demo_result,
        "seller_review": "PENDING",
        "overall_status": overall,
        "browserErrors": browser_errors,
        "droppedWorkflowEvents": replay.get("droppedWorkflowEvents"),
        "live_summary": "proof/live-summary.json",
        "replay_summary": "proof/replay-summary.json",
        "generation_manifest": "proof/generation-manifest.json",
        "seller_review_artifact": "proof/seller-review.json",
        "criteria": {
            "live": live.get("criteria") or {},
            "replay": {
                "functions_disabled": replay.get("functions_disabled"),
                "world_disabled": replay.get("world_disabled"),
                "clean_teardown": replay.get("cleanTeardown"),
            },
        },
    }
    proof_dir.mkdir(parents=True, exist_ok=True)
    (proof_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    _seller_review(proof_dir / "seller-review.json")
    if not PACK_MANIFEST.is_file():
        raise ValueError(f"generation manifest is missing: {PACK_MANIFEST}")
    shutil.copyfile(PACK_MANIFEST, proof_dir / "generation-manifest.json")
    passed = (
        substrate_result == "PASS"
        and demo_result == "PASS"
        and not browser_errors
    )
    return manifest, passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--proof-dir",
        type=Path,
        default=ROOT / "proof",
    )
    parser.add_argument("--dirty-development", action="store_true")
    args = parser.parse_args()
    try:
        _, passed = build_manifest(
            args.proof_dir.resolve(),
            dirty_development=args.dirty_development,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"fashion proof manifest failed: {error}", file=sys.stderr)
        return 2
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

