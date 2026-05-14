#!/usr/bin/env python3
"""pitch-g2 — Build the `vendor-crisis` demo snapshot.

Three vendors flag KYC red simultaneously, which triggers the I2
auto-block ambient-agent path. Run ONCE during demo prep; restore at
demo time with:

    BOOT_DEMO_SNAPSHOT=vendor-crisis make up
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCENARIO = "vendor-crisis"
BASE_URL = "http://localhost:3101"
REPO_ROOT = Path(__file__).resolve().parents[2]
SETTLE_SECONDS = 10

# Three vendors, each in a high-risk jurisdiction so KYC flips red.
RED_VENDORS = [
    {"vendor_name": "Crimson Holdings Ltd", "country": "RU", "scenario": "kyc_red"},
    {"vendor_name": "Sanguine Trading SA",  "country": "IR", "scenario": "kyc_red"},
    {"vendor_name": "Vermillion GmbH",      "country": "KP", "scenario": "kyc_red"},
]


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

    print(f"==> injecting {len(RED_VENDORS)} red-flag vendor-kyc workflows")
    for vendor in RED_VENDORS:
        try:
            res = _post("/api/simulator/fleet-vendor-kyc", vendor)
            print(f"  spawned: {res.get('workflow_id')} ({vendor['vendor_name']})")
        except urllib.error.HTTPError as exc:
            print(f"  warn: vendor-kyc {vendor['vendor_name']} failed: {exc}")

    # Add a few benign vendors so the red ones stand out in the HUD.
    for _ in range(4):
        try:
            _post("/api/simulator/fleet-vendor-kyc", {})
        except urllib.error.HTTPError:
            pass

    print(f"==> sleeping {SETTLE_SECONDS}s for I2 auto-block to fire")
    time.sleep(SETTLE_SECONDS)

    _save_snapshot()
    print(f"\n✓ snapshot ready. Restore with:")
    print(f"    BOOT_DEMO_SNAPSHOT={SCENARIO} make up")


if __name__ == "__main__":
    main()
