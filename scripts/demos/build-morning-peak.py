#!/usr/bin/env python3
"""pitch-g2 — Build the `morning-peak` demo snapshot.

Heavy AP-invoice + employee-onboarding flow at 09:00. Run ONCE during
demo prep against a live stack on http://localhost:3101; the resulting
snapshot is what the operator restores at demo time via:

    BOOT_DEMO_SNAPSHOT=morning-peak make up

The script intentionally does NOT bring the stack up — that's the
operator's job. It only seeds workflows and persists a snapshot.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCENARIO = "morning-peak"
BASE_URL = "http://localhost:3101"
REPO_ROOT = Path(__file__).resolve().parents[2]
SETTLE_SECONDS = 8

AP_INVOICE_COUNT = 25
ONBOARDING_COUNT = 15


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

    print(f"==> injecting {AP_INVOICE_COUNT} AP invoices")
    for i in range(AP_INVOICE_COUNT):
        try:
            _post("/api/simulator/fleet-ap-invoice", {})
        except urllib.error.HTTPError as exc:
            print(f"  warn: ap-invoice #{i} failed: {exc}")

    print(f"==> injecting {ONBOARDING_COUNT} employee-onboarding workflows")
    for i in range(ONBOARDING_COUNT):
        try:
            _post("/api/simulator/fleet-employee-onboarding", {})
        except urllib.error.HTTPError as exc:
            print(f"  warn: onboarding #{i} failed: {exc}")

    print(f"==> sleeping {SETTLE_SECONDS}s for the simulator to process")
    time.sleep(SETTLE_SECONDS)

    _save_snapshot()
    print(f"\n✓ snapshot ready. Restore with:")
    print(f"    BOOT_DEMO_SNAPSHOT={SCENARIO} make up")


if __name__ == "__main__":
    main()
