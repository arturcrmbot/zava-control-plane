"""On-demand dream-pass trigger.

POST /api/dream-pass/run?domain=hiring&sample=10

Runs one dream pass against app_state.dream_pass_orchestrator and
returns a summary. Live progress is observable via the SSE stream
on /api/stream/fleet (event types `dream.*`).

Domain is resolved via api.server.services.dream_pass.skill_loader —
unknown domains produce 422 (skill file missing). Sample size caps the
held-out persona slice the partitioner draws.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.server.routes.dream_pass_pause import is_paused
from api.server.services.dream_pass.skill_loader import (
    DreamSkillLoadError,
    dream_skill_path,
    load_dream_skill,
)
from api.server.state import app_state

router = APIRouter(prefix="/api/dream-pass", tags=["dream-pass"])


@router.post("/run")
async def run_dream_pass(
    domain: str = Query(..., min_length=1),
    sample: int = Query(10, ge=1, le=200),
):
    """Run one dream pass for ``domain`` and return its summary.

    Live progress is observable on the SSE stream `/api/stream/fleet`
    (event types `dream.*`). On unknown ``domain`` returns 422.
    """
    if is_paused(domain):
        raise HTTPException(
            status_code=423,
            detail=f"dream-pass for domain={domain} is paused (kill switch)",
        )
    try:
        skill = load_dream_skill(dream_skill_path(domain))
    except (DreamSkillLoadError, FileNotFoundError) as ex:
        raise HTTPException(status_code=422, detail=str(ex))
    result = await app_state.dream_pass_orchestrator.run_pass(
        skill=skill, sample_size=sample,
    )
    return {
        "dream_pass_id": result.dream_pass_id,
        "domain": result.domain,
        "experiments_run": len(result.experiments),
        "verdict_counts": {
            "promoted": len(result.promoted_lesson_ids),
            "rejected": len(result.rejected_lesson_ids),
            "flagged": len(result.flagged_lesson_ids),
        },
        "promoted_lesson_ids": list(result.promoted_lesson_ids),
        "rejected_lesson_ids": list(result.rejected_lesson_ids),
        "flagged_lesson_ids": list(result.flagged_lesson_ids),
        "experiments": [
            {
                "id": e.id,
                "candidate_lesson_id": e.candidate_lesson_id,
                "control_score": e.control_score,
                "treatment_score": e.treatment_score,
                "delta": e.delta,
                "n_samples": e.n_samples,
                "workflow_ids": list(e.workflow_ids),
                "run_at": e.run_at.isoformat(),
            }
            for e in result.experiments
        ],
    }
