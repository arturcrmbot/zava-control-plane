#!/usr/bin/env python3
"""pitch-g2 — Build the `cfo-month-end-push` demo snapshot.

50+ contract-review approvals queued in one window so the CFO/Finance
HUD shows a credible month-end crunch. Run ONCE during demo prep;
restore at demo time with:

    BOOT_DEMO_SNAPSHOT=cfo-month-end-push make up
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCENARIO = "cfo-month-end-push"
BASE_URL = "http://localhost:3101"
REPO_ROOT = Path(__file__).resolve().parents[2]
SETTLE_SECONDS = 12

CONTRACT_REVIEW_COUNT = 55
TREASURY_FX_COUNT = 8


def _post(path: str, body: dict | None = None, timeout: float = 15.0) -> dict:
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str, timeout: float = 5.0) -> dict:
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _check_stack() -> None:
    try:
        _get("/api/kpis/agency", timeout=3.0)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        sys.exit(
            f"error: stack not reachable at {BASE_URL} ({exc}). "
            "Start it with `make up` first."
        )


def _save_snapshot() -> None:
    print(f"==> saving snapshot '{SCENARIO}' via make snapshot-save")
    subprocess.run(
        ["make", "snapshot-save", f"NAME={SCENARIO}"],
        cwd=REPO_ROOT,
        check=True,
    )


def main() -> None:
    print(f"==> building demo snapshot: {SCENARIO}")
    _check_stack()

    print(f"==> injecting {CONTRACT_REVIEW_COUNT} contract-review workflows")
    failures = 0
    for i in range(CONTRACT_REVIEW_COUNT):
        try:
            _post("/api/simulator/fleet-contract-review", {})
        except urllib.error.HTTPError as exc:
            failures += 1
            if failures <= 3:
                print(f"  warn: contract-review #{i} failed: {exc}")
    print(f"  spawned ~{CONTRACT_REVIEW_COUNT - failures} contract-reviews")

    print(f"==> injecting {TREASURY_FX_COUNT} treasury-fx workflows")
    for _ in range(TREASURY_FX_COUNT):
        try:
            _post("/api/simulator/fleet-treasury-fx", {})
        except urllib.error.HTTPError:
            pass

    print(f"==> sleeping {SETTLE_SECONDS}s for the simulator to process")
    time.sleep(SETTLE_SECONDS)

    _save_snapshot()
    print(f"\n✓ snapshot ready. Restore with:")
    print(f"    BOOT_DEMO_SNAPSHOT={SCENARIO} make up")


if __name__ == "__main__":
    main()
