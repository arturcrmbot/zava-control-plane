"""Learning-loop diagnostics surface (Track I).

Each pitch-i task installs a small learning loop in the substrate (cache
warming, rule emergence, trend triggers, replay). This router exposes
read-only diagnostics so the j6 learning panel can render the loops in
real time. Other Track I agents extend this router with additional
endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter

from api.server.services import classifier_cache
from api.server.services import persona_experience, routing_stats

router = APIRouter(prefix="/api/learning")


@router.get("/classifier-cache-stats")
async def classifier_cache_stats() -> dict:
    """Return live ``exception-classifier`` cache size + hit/miss counters."""
    return classifier_cache.stats()


@router.get("/routing-stats")
def get_routing_stats() -> dict:
    """Per-(domain, gate, role) approval-rate matrix produced by I4.

    Empty on a cold start — fills in as personae decide. Each row carries
    ``approves`` / ``total`` / ``approval_rate`` so the j6 panel can
    render deltas without re-deriving them.
    """
    return {
        "stats": routing_stats.snapshot(),
        "min_samples_for_routing": routing_stats.MIN_SAMPLES,
    }


@router.get("/persona-experience")
def get_persona_experience() -> dict:
    """Per-persona / per-domain decision count produced by I6."""
    return {"experience": persona_experience.snapshot()}
