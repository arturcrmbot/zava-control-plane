"""End-to-end dream-pass demo — seeds realistic working memories,
optionally triggers a pass, prints before/after lesson counts.

Usage:
    # via running FastAPI on :3101 (recommended — exercises the real path):
    uv run python scripts/dream_pass_demo.py --base http://localhost:3101

    # or in-process (no HTTP, useful for CI smoke):
    uv run python scripts/dream_pass_demo.py --in-process

The seed deliberately writes a clustered set of decisions across two
personae so the rule-based fallback consolidator can compress them
into observable LESSON entries. After the pass:

  GET /api/memory/working-notes?domain=hiring   → fewer / zero rows
  GET /api/memory/lessons/active?domain=hiring  → ≥1 LESSON row
  GET /api/memory/per-persona                   → recruiter lessons > 0
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

import httpx


# Realistic clustered hiring memories. Two clusters around CV-screen
# rejects + one offer-decision approve cluster so the consolidator can
# emit two distinct LESSON entries.
SEED_MEMORIES: list[dict[str, Any]] = [
    # Cluster 1 — recruiter rejects on weak voice signal
    {"role": "recruiter", "verdict": "reject", "gate": "cv_screen",
     "reason": "voice signal weak", "signals": {"voice_score": 1.2, "cv_score": 2},
     "workflow_id": "W-CV-001"},
    {"role": "recruiter", "verdict": "reject", "gate": "cv_screen",
     "reason": "voice signal weak", "signals": {"voice_score": 1.4, "cv_score": 1},
     "workflow_id": "W-CV-002"},
    {"role": "recruiter", "verdict": "reject", "gate": "cv_screen",
     "reason": "voice signal weak", "signals": {"voice_score": 1.8, "cv_score": 2},
     "workflow_id": "W-CV-003"},
    {"role": "recruiter", "verdict": "reject", "gate": "cv_screen",
     "reason": "voice signal weak", "signals": {"voice_score": 1.1, "cv_score": 3},
     "workflow_id": "W-CV-004"},
    # Cluster 2 — hiring_manager approves at offer stage with high scores
    {"role": "hiring_manager", "verdict": "approve", "gate": "offer_decision",
     "reason": "strong all-round", "signals": {"voice_score": 4.5, "cv_score": 5},
     "workflow_id": "W-OFF-101"},
    {"role": "hiring_manager", "verdict": "approve", "gate": "offer_decision",
     "reason": "strong all-round", "signals": {"voice_score": 4.7, "cv_score": 5},
     "workflow_id": "W-OFF-102"},
    {"role": "hiring_manager", "verdict": "approve", "gate": "offer_decision",
     "reason": "strong all-round", "signals": {"voice_score": 4.2, "cv_score": 4},
     "workflow_id": "W-OFF-103"},
    # Single outlier — should pass through unchanged
    {"role": "talent_lead", "verdict": "escalate", "gate": "panel_review",
     "reason": "unusual background needs review",
     "signals": {"cv_score": 3},
     "workflow_id": "W-PNL-201"},
]


def _seed_in_process(domain: str) -> int:
    """Write seed entries directly to the DomainMemory store."""
    from api.server.services.memory.fallback_memory import get_fallback_memory
    from api.server.services.memory.domain_memory import DomainMemory

    store = DomainMemory(domain=domain, memory=get_fallback_memory())
    for m in SEED_MEMORIES:
        sig = ", ".join(f"{k}={v}" for k, v in (m["signals"] or {}).items())
        text = (
            f"[{m['role']}] {m['verdict'].upper()} for {m['gate']} — "
            f"{m['reason']} — signals: {sig}"
        )
        store.add(text, agent_skill=f"persona:{m['role']}", workflow_id=m["workflow_id"])
    return len(SEED_MEMORIES)


async def _run_in_process_pass(domain: str) -> dict:
    from api.server.services.memory.fallback_memory import get_fallback_memory
    from api.server.services.memory.domain_memory import DomainMemory
    from api.server.services.memory.dream_consolidator import consolidate_memories
    from api.server.services.memory.fallback_consolidator import fallback_consolidate

    store = DomainMemory(domain=domain, memory=get_fallback_memory())

    async def _fb(texts: list[str]) -> list[str]:
        return fallback_consolidate(texts)

    return await consolidate_memories(domain_memory=store, llm_consolidate=_fb)


def _seed_http(base: str, domain: str) -> int:
    """Write seed entries via the running API.

    We POST through a dedicated demo route. If unavailable, fall back to
    writing in-process (only works if the script runs in the same Python
    process as the API, which it usually doesn't — so prefer in-process
    seeding for HTTP mode or run the script with --in-process).
    """
    # Simplest: use the in-process path so the demo is self-contained.
    # The cadence loop in the running API will then organically pick up
    # the backlog and fire a real dream pass.
    raise SystemExit(
        "HTTP seeding requires a backend route that doesn't exist yet. "
        "Use --in-process and run this script in the same venv as the "
        "FastAPI, or wire scripts/dream_pass_demo.py into a Make target."
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:3101")
    p.add_argument("--domain", default="hiring")
    p.add_argument("--in-process", action="store_true",
                   help="Skip HTTP, write directly into the in-process FallbackMemory.")
    p.add_argument("--trigger", action="store_true",
                   help="Also explicitly trigger a dream pass after seeding.")
    p.add_argument("--no-trigger", dest="trigger", action="store_false")
    p.set_defaults(trigger=True)
    args = p.parse_args()

    print(f"[demo] seeding {len(SEED_MEMORIES)} memories for domain={args.domain}")

    if args.in_process:
        seeded = _seed_in_process(args.domain)
        print(f"[demo] in-process: seeded {seeded} entries")

        if args.trigger:
            print("[demo] running dream pass in-process …")
            result = asyncio.run(_run_in_process_pass(args.domain))
            print(f"[demo] result: {json.dumps(result, indent=2)}")

            from api.server.services.memory.domain_memory import DomainMemory
            from api.server.services.memory.fallback_memory import get_fallback_memory

            store = DomainMemory(domain=args.domain, memory=get_fallback_memory())
            print(f"[demo] working memories remaining: {store.count_working()}")
            print(f"[demo] distilled lessons: {len(store.list_by_kind('lesson'))}")
            for lesson in store.list_by_kind("lesson"):
                print(f"  • {lesson['memory']}")
        return 0

    # HTTP mode: seed via in-process (script & API typically not co-located,
    # but this still demos the cadence loop end-to-end). For demos run
    # ./scripts/boot-demo.sh first, then run this script in the SAME venv
    # — the fallback_memory singleton lives per-process so we can't share
    # it across uvicorn + this CLI. So the HTTP path triggers via the
    # /api/memory/v2/dream route after writing through it.
    print(f"[demo] HTTP mode against {args.base}")
    seed_count = 0
    with httpx.Client(timeout=30.0) as cli:
        # Write via the /api/memory/v2/dream route which exists; but we
        # need a write endpoint for working memories. Use the new
        # /api/memory/seed-demo endpoint defined alongside this script.
        r = cli.post(
            f"{args.base}/api/memory/seed-demo",
            json={"domain": args.domain, "entries": SEED_MEMORIES},
        )
        if r.status_code == 404:
            print(
                "[demo] /api/memory/seed-demo not found — using --in-process "
                "is the recommended path. Aborting HTTP seed."
            )
            return 2
        r.raise_for_status()
        seed_count = r.json().get("written", 0)
        print(f"[demo] HTTP: seeded {seed_count} entries")

        if args.trigger:
            print(f"[demo] triggering dream pass via /api/memory/v2/dream …")
            r = cli.post(
                f"{args.base}/api/memory/v2/dream",
                json={"domain": args.domain},
            )
            r.raise_for_status()
            print(f"[demo] result: {json.dumps(r.json(), indent=2)}")

        # Snapshot
        r = cli.get(f"{args.base}/api/memory/working-notes?domain={args.domain}")
        wn = r.json().get("items", [])
        r = cli.get(f"{args.base}/api/memory/lessons/active?domain={args.domain}")
        lessons = r.json().get("items", [])
        print(f"[demo] working notes now: {len(wn)}")
        print(f"[demo] distilled lessons: {len(lessons)}")
        for l in lessons:
            print(f"  • {l['memory']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
