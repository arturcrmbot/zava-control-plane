#!/usr/bin/env python3
"""pitch-g2 — Build the `creative-awards-week` demo snapshot.

A wave of creative work lighting up the agency persona view: many
creative-campaign workflows plus successive `inject-burst` calls so the
cosmic lens shows a sustained creative + media-pitch swell. Run ONCE
during demo prep; restore at demo time with:

    BOOT_DEMO_SNAPSHOT=creative-awards-week make up

Note: as of pitch-g2 there is no dedicated HTTP route for
``creative-awards-submission`` / ``media-pitch-to-win`` (those domains
spawn through the cadenced-rituals scheduler, not the inject API). The
script seeds a creative-heavy mix via the available endpoints; the
ambient cadence will fold in the awards-submission and pitch-to-win
workflows on its own once the snapshot is restored and time advances.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCENARIO = "creative-awards-week"
BASE_URL = "http://localhost:3101"
REPO_ROOT = Path(__file__).resolve().parents[2]
SETTLE_SECONDS = 10

CREATIVE_CAMPAIGN_COUNT = 18
BURST_ROUNDS = 4


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

    print(f"==> injecting {CREATIVE_CAMPAIGN_COUNT} creative-campaign workflows")
    for i in range(CREATIVE_CAMPAIGN_COUNT):
        try:
            _post("/api/simulator/creative-campaign", {})
        except urllib.error.HTTPError as exc:
            if i < 3:
                print(f"  warn: creative-campaign #{i} failed: {exc}")

    print(f"==> firing {BURST_ROUNDS} inject-burst rounds for varied activity")
    for r in range(BURST_ROUNDS):
        try:
            _post("/api/simulator/inject-burst?n=8", {})
        except urllib.error.HTTPError as exc:
            print(f"  warn: burst round {r} failed: {exc}")
        time.sleep(1.0)

    print(f"==> sleeping {SETTLE_SECONDS}s for the simulator to process")
    time.sleep(SETTLE_SECONDS)

    _save_snapshot()
    print(f"\n✓ snapshot ready. Restore with:")
    print(f"    BOOT_DEMO_SNAPSHOT={SCENARIO} make up")


if __name__ == "__main__":
    main()
