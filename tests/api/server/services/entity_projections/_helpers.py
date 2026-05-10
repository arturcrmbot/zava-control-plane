"""Shared helpers for per-domain projection tests.

A tiny ``make_workflow`` factory builds a :class:`Workflow` from a payload
dict so the per-domain test files don't repeat the boilerplate. The factory
defaults the platform-required fields (``jurisdiction``, ``agency``,
``created_at``, ``sla_due_at``) so test bodies can focus on the domain
payload they care about.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from api.shared.types import Workflow

_REPO_ROOT = Path(__file__).resolve().parents[5]


def fixture_payload(domain: str, fname: str, idx: int = 0) -> dict[str, Any]:
    """Load row ``idx`` from ``data/synthetic/<domain>/<fname>``."""
    path = _REPO_ROOT / "data" / "synthetic" / domain / fname
    with path.open() as f:
        rows = json.load(f)
    return dict(rows[idx])


def make_workflow(
    workflow_id: str,
    workflow_type: str,
    payload: dict[str, Any],
    *,
    decisions: list[dict[str, Any]] | None = None,
) -> Workflow:
    now = time.time()
    full_payload = dict(payload)
    if decisions is not None:
        full_payload["decisions"] = decisions
    return Workflow(
        id=workflow_id,
        type=workflow_type,
        current_phase="Intake",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-Test",
        payload=full_payload,
    )
