"""Bus event type constants for the dream-pass loop.

Every stage in DreamPassOrchestrator.run_pass emits one of these onto
app_state.bus so the live SSE stream (and the Fleet UI Memory page)
can show dreaming as it happens.
"""
from __future__ import annotations

DREAM_PASS_STARTED      = "dream.pass.started"
DREAM_PROPOSAL_GENERATED = "dream.proposal.generated"
DREAM_EXPERIMENT_SCORED  = "dream.experiment.scored"
DREAM_LESSON_PROMOTED    = "dream.lesson.promoted"
DREAM_LESSON_REJECTED    = "dream.lesson.rejected"
DREAM_PASS_FINISHED      = "dream.pass.finished"

ALL_DREAM_EVENT_TYPES: tuple[str, ...] = (
    DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
    DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
)
