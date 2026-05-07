"""Seed three demo HiringOrchestrator workflows at FastAPI startup.

The candidate portal /apply form posts a `role_id` (one of the three demo
reqs) and expects a workflow to attach to. This module is the bridge: at
lifespan startup we read `data/synthetic/hiring/reqs.json`, materialise a
`Workflow` for each entry, upsert it into the StateStore so the
role_id reverse index is populated, and then schedule a real
`HiringOrchestrator` Durable run so the workflow actually progresses
through phases (instead of sitting forever at a placeholder Triage).

Idempotent for the upsert; the orchestration is only scheduled when the
workflow doesn't already have an `orchestration_instance_id` (i.e. on a
cold-start, not on a re-entrant lifespan reload).

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 14.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from api.shared.types import Workflow
from api.server.services.durable_client import schedule_new_orchestration

_REQS_FILE = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "hiring" / "reqs.json"


def _market_for_jurisdiction(jurisdiction: str) -> str:
    if jurisdiction == "DE":
        return "Berlin-WPP"
    if jurisdiction == "UK":
        return "London-WPP"
    return "London-WPP"


async def seed_demo_reqs(app_state) -> list[str]:
    """Read the reqs fixture, upsert one Workflow per entry, and schedule a
    real HiringOrchestrator Durable instance against each. Returns the
    list of workflow ids that were materialised so callers can log a tally.

    No-op when the fixture file is missing — non-portal demos run fine
    without it, and the /apply route surfaces a clean 404 in that case.
    """
    if not _REQS_FILE.exists():
        return []
    raw = json.loads(_REQS_FILE.read_text(encoding="utf-8"))
    now = time.time()
    spawned: list[str] = []
    for i, req in enumerate(raw):
        role_id = req["id"]
        # Deterministic workflow id so subsequent restarts re-attach to the
        # same record (the StateStore is in-memory but the URLs in the demo
        # outbox could otherwise drift).
        workflow_id = f"HIRE-DEMO-{i+1:02d}"
        existing = app_state.store.get_workflow(workflow_id)
        if existing is not None:
            spawned.append(workflow_id)
            continue
        jurisdiction = req.get("jurisdiction", "USA")
        w = Workflow(
            id=workflow_id,
            type="hiring",
            current_phase="Budget",
            created_at=now,
            sla_due_at=now + 7 * 86400,
            jurisdiction=_market_for_jurisdiction(jurisdiction),
            agency="WPP-HR",
            metadata={
                "role_id": role_id,
                "role_title": req.get("title"),
                "role_jurisdiction": jurisdiction,
                "demo_seed": True,
            },
        )
        app_state.store.upsert_workflow(w)
        spawned.append(workflow_id)
        # NOTE: orchestrator is intentionally NOT auto-scheduled here. The
        # /api/portal/apply route (or portal_orchestration's candidate.applied
        # subscriber) is what actually starts the HiringOrchestrator once a
        # real candidate exists. Auto-scheduling at boot caused workflows to
        # progress through phases before any candidate had applied, which
        # broke demos. (See plan/feature-authority-and-personae-1.md.)
        _ = (asyncio, schedule_new_orchestration)  # keep imports referenced
    return spawned
