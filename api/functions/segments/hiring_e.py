"""Hiring Segment E — compliance + offer prep."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


_SEGMENT_E_SKILLS: list[str] = ["jurisdiction-router", "betrvg-checker", "offer-personaliser"]
_SEGMENT_E_MCPS: list[str] = ["policy.search"]


class SegmentEOutput(BaseModel):
    offer_letter_id: str
    jurisdiction: Literal["USA", "DE"]
    compliance_steps: list[str]
    policy_citations: list[str]


def _skills_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "server" / "skills"


def _build_segment_e_prompt(enriched: dict, prior_validator_error: str | None = None) -> str:
    schema = SegmentEOutput.model_json_schema()
    parts = [
        "You are preparing the offer letter and running jurisdiction compliance.",
        "",
        "Context:",
        repr({k: enriched.get(k) for k in ("req_id", "candidate_id", "jurisdiction", "offer_decision") if k in enriched}),
        "",
        f"Available skills: {', '.join(_SEGMENT_E_SKILLS)}",
        f"Available MCPs (call as needed): {', '.join(_SEGMENT_E_MCPS)}",
        "",
        "Deliverable — return ONE JSON object matching this schema:",
        repr(schema),
        "",
        "Return only the JSON object. No preamble.",
    ]
    if prior_validator_error:
        parts.extend(["", "Previous attempt failed validation:", prior_validator_error])
    return "\n".join(parts)


async def run_segment_e(input: dict) -> dict:
    from api.functions.graphs.executors.agents._wrapper import run_agent_session
    skills_root = _skills_dir()
    skill_dirs = [skills_root / s for s in _SEGMENT_E_SKILLS]
    prompt = _build_segment_e_prompt(input, prior_validator_error=input.get("prior_validator_error"))
    return await run_agent_session(
        prompt=prompt,
        tools=[],
        skill_dir=skill_dirs[0],
        skill_directories=skill_dirs[1:],
        skill_label="hiring-segment-e",
        workflow_id=input.get("workflow_id"),
        instance_id=input.get("instance_id"),
        covered_phases=input.get("covered_phases"),
        model="gpt-4.1",
    )
