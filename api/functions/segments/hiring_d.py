"""Hiring Segment D — interview decisioning."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


_SEGMENT_D_SKILLS: list[str] = ["interview-recommender"]
_SEGMENT_D_MCPS: list[str] = []


class SegmentDOutput(BaseModel):
    decision: Literal["advance", "reject", "escalate"]
    interview_recommendation: dict
    rationale: str


def _skills_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "server" / "skills"


def _build_segment_d_prompt(enriched: dict, prior_validator_error: str | None = None) -> str:
    schema = SegmentDOutput.model_json_schema()
    parts = [
        "You are deciding whether to advance a candidate to interview.",
        "",
        "Context:",
        repr({k: enriched.get(k) for k in ("req_id", "candidate_id", "screening_verdict") if k in enriched}),
        "",
        f"Available skills: {', '.join(_SEGMENT_D_SKILLS)}",
        "",
        "Deliverable — return ONE JSON object matching this schema:",
        repr(schema),
        "",
        "Return only the JSON object. No preamble.",
    ]
    if prior_validator_error:
        parts.extend(["", "Previous attempt failed validation:", prior_validator_error])
    return "\n".join(parts)


async def run_segment_d(input: dict) -> dict:
    from api.functions.graphs.executors.agents._wrapper import run_agent_session
    skills_root = _skills_dir()
    skill_dirs = [skills_root / s for s in _SEGMENT_D_SKILLS]
    prompt = _build_segment_d_prompt(input, prior_validator_error=input.get("prior_validator_error"))
    return await run_agent_session(
        prompt=prompt, tools=[], skill_dir=skill_dirs[0],
        skill_label="hiring-segment-d", workflow_id=input.get("workflow_id"),
        instance_id=input.get("instance_id"),
        covered_phases=input.get("covered_phases"),
        model="gpt-4.1",
    )
