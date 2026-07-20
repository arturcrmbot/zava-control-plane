"""Assemble proof/manifest.json for the Fashion vertical from the live evidence
the Playwright driver produced. The manifest is PASS only when every phase, the
browser-error gate and the teardown passed; otherwise it is FAIL and this script
exits non-zero. Nothing here invents a verdict — it aggregates observed JSON."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES

CONTRACT_WORKFLOWS = list(FASHION_PROCESS_PROFILES)


OUT_DIR = Path(os.environ["PROOF_OUT_DIR"]).resolve()
SOURCE_COMMIT = os.environ.get("SOURCE_COMMIT", "")
TEARDOWN_STATUS = os.environ.get("TEARDOWN_STATUS", "FAIL")
PORTS_RELEASED = os.environ.get("PORTS_RELEASED", "unknown")

EVIDENCE = [
    "summary.json",
    "world-state.json",
    "world-journal.json",
    "durable-instances.json",
    "entity-graph.json",
    "memory.json",
    "replay-summary.json",
    "functions-disabled.json",
    "recordings",
    "screenshots",
    "video",
    "logs",
]


def _load(name: str) -> dict:
    path = OUT_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def main() -> int:
    summary = _load("summary.json")
    functions_disabled = _load("functions-disabled.json")
    replay = _load("replay-summary.json")

    live = "PASS" if summary.get("result") == "PASS" else "FAIL"
    fd_status = "PASS" if functions_disabled.get("result") == "PASS" else "FAIL"
    aw_status = "PASS" if replay.get("result") == "PASS" else "FAIL"
    replay_status = "PASS" if fd_status == "PASS" and aw_status == "PASS" else "FAIL"

    workflows = summary.get("workflows", {})
    browser_errors = list(summary.get("browserErrors", []))
    browser_errors += list(functions_disabled.get("browserErrors", []))
    browser_errors += list(replay.get("browserErrors", []))

    dropped = 0
    for entry in workflows.values():
        surfaces = entry.get("surfaces", {})
        if surfaces.get("constellation") != "PASS":
            dropped += 1

    all_workflows_present = set(workflows) == set(CONTRACT_WORKFLOWS)
    all_workflows_pass = all(
        entry.get("status") == "PASS" for entry in workflows.values()
    )

    browser_status = "PASS" if not browser_errors and dropped == 0 else "FAIL"
    teardown_status = "PASS" if TEARDOWN_STATUS == "PASS" else "FAIL"

    status = (
        "PASS"
        if (
            live == "PASS"
            and replay_status == "PASS"
            and browser_status == "PASS"
            and teardown_status == "PASS"
            and all_workflows_present
            and all_workflows_pass
        )
        else "FAIL"
    )

    evidence_paths = [name for name in EVIDENCE if (OUT_DIR / name).exists()]

    manifest = {
        "vertical": "fashion",
        "source_commit": SOURCE_COMMIT,
        "status": status,
        "live": live,
        "replay": replay_status,
        "browser_errors": browser_errors,
        "workflows": {
            wtype: {
                "status": entry.get("status"),
                "workflow_id": entry.get("workflow_id"),
                "surfaces": entry.get("surfaces", {}),
                "chain": entry.get("chain", {}),
            }
            for wtype, entry in workflows.items()
        },
        "replay_probes": {
            "functions_disabled": fd_status,
            "actor_world_disabled": aw_status,
        },
        "browser": {
            "console_errors": len(browser_errors),
            "dropped_workflow_events": dropped,
            "status": browser_status,
        },
        "teardown": {
            "status": teardown_status,
            "ports_released": PORTS_RELEASED,
        },
        "evidence_paths": evidence_paths,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": status, "live": live, "replay": replay_status}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
