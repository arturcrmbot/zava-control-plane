"""api/server/data_fabric/workflow_timeline.py — 24-h workflow spawn fabric.

Generates the historical + in-flight workflow timeline used to seed the
substrate at boot. Per-domain frequency follows
``api.shared.domains.DOMAINS[wt].realistic_interval_seconds`` so a hot
domain (e.g. ``creative-campaign`` at 30 min) produces many more rockets
than a cold one (e.g. ``contract-renewal`` at 60 days).

Plan: plan/feature-enterprise-pitch-readiness-1.md (task ``pitch-b7``).
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.shared.domains import DOMAINS, Domain
from api.shared.types import Workflow

__all__ = ["TimelineEntry", "generate_timeline"]


@dataclass(frozen=True)
class TimelineEntry:
    workflow: Workflow
    completed: bool
    spawned_at: datetime
    completed_at: datetime | None


# Repo root → data/synthetic/<workflow_type>/*.json. Resolved lazily.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_ROOT = _REPO_ROOT / "data" / "synthetic"


def _live_domains() -> list[Domain]:
    return [d for d in DOMAINS.values() if not d.stub]


def _domain_weights(live: list[Domain]) -> list[float]:
    out: list[float] = []
    for d in live:
        interval = d.realistic_interval_seconds or 86_400
        out.append(1.0 / float(interval))
    return out


def _allocate(weights: list[float], total: int, *, ensure_minimum_one: bool) -> list[int]:
    """Hamilton-style deterministic allocation of ``total`` across the
    weight buckets. When ``ensure_minimum_one`` is set every bucket gets
    at least one allocation (capped to ``total`` when there are fewer
    items than buckets)."""
    n = len(weights)
    if n == 0 or total <= 0:
        return [0] * n
    weight_sum = sum(weights) or 1.0

    if ensure_minimum_one:
        if total <= n:
            # Fall back to round-robin so the first ``total`` buckets each
            # get a single entry. Keeps determinism.
            base = [0] * n
            for i in range(total):
                base[i] = 1
            return base
        base = [1] * n
        remaining = total - n
    else:
        base = [0] * n
        remaining = total

    raw = [w / weight_sum * remaining for w in weights]
    floors = [int(r) for r in raw]
    allocated_extra = sum(floors)
    leftover = remaining - allocated_extra
    # Distribute leftover by largest fractional residual (deterministic
    # because we tie-break on bucket index).
    fractional = sorted(
        ((raw[i] - floors[i], i) for i in range(n)),
        key=lambda t: (-t[0], t[1]),
    )
    for k in range(leftover):
        floors[fractional[k][1]] += 1
    return [b + e for b, e in zip(base, floors)]


def _load_payload_pool(workflow_type: str) -> list[dict]:
    """Best-effort sample-pool loader. Returns ``[]`` when the domain
    has no data/synthetic/<wt>/*.json fixtures."""
    folder = _FIXTURE_ROOT / workflow_type
    if not folder.is_dir():
        return []
    pool: list[dict] = []
    for path in sorted(folder.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as fh:
                blob = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(blob, list):
            pool.extend(item for item in blob if isinstance(item, dict))
        elif isinstance(blob, dict):
            pool.append(blob)
    return pool


def _make_workflow(
    *,
    domain: Domain,
    counter: int,
    spawned_at: datetime,
    completed: bool,
    payload: dict,
    rng: random.Random,
) -> Workflow:
    sla_window = timedelta(seconds=max(domain.realistic_interval_seconds or 86_400, 3_600))
    sla_due_at = spawned_at + sla_window
    initial_phase = domain.phases[0].name if domain.phases else "Intake"
    if completed:
        status = "completed"
        current_phase = domain.phases[-1].name if domain.phases else initial_phase
    else:
        status = "in_progress"
        # Pick a deterministic in-progress phase mid-flow.
        if len(domain.phases) > 1:
            idx = rng.randint(0, len(domain.phases) - 1)
            current_phase = domain.phases[idx].name
        else:
            current_phase = initial_phase
    workflow_id = f"{domain.workflow_id_prefix}-{counter:04d}"
    return Workflow(
        id=workflow_id,
        type=domain.workflow_type,
        status=status,
        current_phase=current_phase,
        created_at=spawned_at.timestamp(),
        sla_due_at=sla_due_at.timestamp(),
        payload=dict(payload) if payload else {},
        jurisdiction="UK",
        agency="zava-group",
    )


def generate_timeline(
    *,
    seed: int,
    end_time: datetime | None = None,
    in_flight_count: int = 25,
    historical_count: int = 125,
) -> list[TimelineEntry]:
    """Materialise ~150 deterministic timeline entries.

    ``historical_count`` workflows are spawned uniformly at random in the
    24h window ending at ``end_time`` (defaults to now-UTC) and marked
    completed. ``in_flight_count`` workflows are spawned uniformly at
    random in the 1–2h window ending at ``end_time`` and left
    in-progress.
    """
    rng = random.Random(seed)
    if end_time is None:
        end_time = datetime.now(timezone.utc)
    elif end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    live = _live_domains()
    if not live:
        return []
    weights = _domain_weights(live)

    historical_alloc = _allocate(weights, historical_count, ensure_minimum_one=True)
    in_flight_alloc = _allocate(weights, in_flight_count, ensure_minimum_one=False)

    entries: list[TimelineEntry] = []
    historical_window_start = end_time - timedelta(hours=24)
    inflight_window_start = end_time - timedelta(hours=2)
    inflight_window_end = end_time - timedelta(hours=1)

    for domain, hist_n, flight_n in zip(live, historical_alloc, in_flight_alloc):
        pool = _load_payload_pool(domain.workflow_type)
        counter = 0

        # --- historical ---
        for _ in range(hist_n):
            counter += 1
            offset = rng.uniform(0, 24 * 3600)
            spawned_at = historical_window_start + timedelta(seconds=offset)
            duration = rng.uniform(60, max(3_600.0, (domain.realistic_interval_seconds or 86_400) / 2))
            completed_at = spawned_at + timedelta(seconds=duration)
            if completed_at > end_time:
                completed_at = end_time
            payload = pool[rng.randint(0, len(pool) - 1)] if pool else {}
            wf = _make_workflow(
                domain=domain,
                counter=counter,
                spawned_at=spawned_at,
                completed=True,
                payload=payload,
                rng=rng,
            )
            entries.append(
                TimelineEntry(
                    workflow=wf,
                    completed=True,
                    spawned_at=spawned_at,
                    completed_at=completed_at,
                )
            )

        # --- in-flight ---
        for _ in range(flight_n):
            counter += 1
            offset = rng.uniform(0, (inflight_window_end - inflight_window_start).total_seconds())
            spawned_at = inflight_window_start + timedelta(seconds=offset)
            payload = pool[rng.randint(0, len(pool) - 1)] if pool else {}
            wf = _make_workflow(
                domain=domain,
                counter=counter,
                spawned_at=spawned_at,
                completed=False,
                payload=payload,
                rng=rng,
            )
            entries.append(
                TimelineEntry(
                    workflow=wf,
                    completed=False,
                    spawned_at=spawned_at,
                    completed_at=None,
                )
            )

    entries.sort(key=lambda e: (e.spawned_at, e.workflow.id))
    return entries
