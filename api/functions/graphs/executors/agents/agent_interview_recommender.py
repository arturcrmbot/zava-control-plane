"""POC2 Phase 7 — interview-recommender executor.

Runs at two distinct gates (`post_voice`, `post_interview`) under
current_phase=Interview. Builds a single prompt that names the gate and
forwards all available context, calls the cv-crystalliser-style wrapper,
and returns the structured JSON for the recruiter UI to render.

Failure mode: when the wrapper returns parse_error, we return a synthetic
"recommender_status: failed" payload so the recruiter view paints a
clear "rec unavailable" state instead of either crashing or fabricating
a recommendation.
"""
from __future__ import annotations

import json

from api.shared.role_levels import levels_for

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "interview-recommender"


def _build_prompt(input: dict) -> str:
    gate = input.get("gate") or "post_voice"
    role_title = input.get("role_title") or "Candidate"
    role_jurisdiction = input.get("role_jurisdiction") or "—"
    levels = levels_for(role_title)
    payload = {
        "gate": gate,
        "role_title": role_title,
        "role_jurisdiction": role_jurisdiction,
        "levels_for_role": levels,
        "cv_crystalliser": input.get("cv_crystalliser") or {},
        "screening": input.get("screening") or {},
        "voice_transcript": input.get("voice_transcript") or [],
        "voice_score": input.get("voice_score"),
        "lessons": input.get("lessons") or [],
        "working_notes": input.get("working_notes") or [],
    }
    return (
        f"Recommend at gate `{gate}` for `{role_title}`. "
        f"Context (JSON):\n```json\n{json.dumps(payload, indent=2)}\n```\n"
        f"Return ONLY the JSON object specified in your skill — no prose, "
        f"no markdown fences."
    )


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id") or input.get("hire_id")
    if not workflow_id:
        return {"interview_recommender": None}

    parsed = await run_agent_session(
        prompt=_build_prompt(input),
        tools=[],
        skill_dir=_SKILL_DIR,
        skill_label="interview_recommender",
        workflow_id=workflow_id,
    )

    parse_failed = (
        not isinstance(parsed, dict)
        or parsed.get("parse_error")
        or "decision" not in parsed
    )
    if parse_failed:
        return {
            "interview_recommender": {
                "decision": "advance",
                "level_suggestion": None,
                "rationale": "Recommender output unparseable — defaulting to advance so candidates are not penalised by system errors. See agent_reasoning trace.",
                "talking_points": ["verify CV details manually", "confirm screening outcome in interview"],
                "recommender_status": "failed",
            }
        }

    parsed.setdefault("recommender_status", "ok")
    return {"interview_recommender": parsed}
