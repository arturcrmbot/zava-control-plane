# api/functions/segments/hiring_b.py
"""Hiring Segment B — candidate discovery as one agentic loop.

Phase 3 of plan/refactor-substrate-agentic-segments-1.md.

Replaces the four per-phase activities (Job Design, Sourcing, Triage,
Screening) with one segment activity that opens one CopilotSession
loaded with all four skills + the two MCPs they call. The model
decides invocation order; the orchestrator owns segment boundaries,
HITL, retry, audit.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


_SEGMENT_B_SKILLS: list[str] = [
    "jd-drafter",
    "sourcing-orchestrator",
    "cv-crystalliser",
    "auto-shortlister",
]
_SEGMENT_B_MCPS: list[str] = ["policy.search", "ocr.extract"]


class CandidateScore(BaseModel):
    id: str
    score: float = Field(ge=0.0, le=1.0)
    rationale: str


class SegmentBOutput(BaseModel):
    verdict: Literal["low", "borderline", "strong"]
    jd_draft_id: str
    sourcing_pool_id: str
    candidates: list[CandidateScore]
    rationale: str

    @field_validator("candidates")
    @classmethod
    def _at_least_one(cls, v: list[CandidateScore]) -> list[CandidateScore]:
        if not v:
            raise ValueError("candidates: at least one required")
        return v


def _skills_dir() -> Path:
    """Return the on-disk skills directory used by the GHCP SDK to
    auto-discover SKILL.md files. Mirrors `_wrapper.py:_SKILLS_DIR`."""
    return Path(__file__).resolve().parents[2] / "server" / "skills"


def _build_segment_b_prompt(
    enriched: dict,
    prior_validator_error: str | None = None,
) -> str:
    """Goal-shaped prompt. Names the deliverable + the available
    skills/MCPs by name; does NOT prescribe invocation order — that's
    the agentic loop's job.

    If the previous attempt failed validation, append the validator
    error so the model can adapt within the retry."""
    schema = SegmentBOutput.model_json_schema()
    req_summary = {
        k: enriched.get(k) for k in (
            "req_id", "role", "jurisdiction", "budget_envelope",
        ) if k in enriched
    }
    parts: list[str] = [
        "You are handling candidate discovery for a requisition.",
        "",
        "Requisition brief:",
        repr(req_summary),
        "",
        f"Available skills (load on demand): {', '.join(_SEGMENT_B_SKILLS)}",
        f"Available MCPs (call as needed): {', '.join(_SEGMENT_B_MCPS)}",
        "",
        "Deliverable — return ONE JSON object matching this schema:",
        repr(schema),
        "",
        "Return only the JSON object. No preamble.",
    ]
    if prior_validator_error:
        parts.extend([
            "",
            "Your previous attempt failed validation with the following error.",
            "Produce a valid output this time:",
            prior_validator_error,
        ])
    return "\n".join(parts)


async def run_segment_b(input: dict) -> dict:
    """Open one agent session loaded with all 4 Segment B skills, send
    the goal-shaped prompt, return the parsed response."""
    from api.functions.graphs.executors.agents._wrapper import run_agent_session

    skills_root = _skills_dir()
    skill_dirs = [skills_root / s for s in _SEGMENT_B_SKILLS]
    # The wrapper accepts ONE skill_dir today; we pass the first as the
    # primary skill_dir for SKILL.md loading and rely on
    # skill_directories= in the runtime kwargs for auto-discovery of
    # the rest. (Phase 2's runtime accepts skill_directories= as a list.)
    prior_err = input.get("prior_validator_error")
    prompt = _build_segment_b_prompt(input, prior_validator_error=prior_err)

    return await run_agent_session(
        prompt=prompt,
        tools=[],  # Tool objects resolved by the SDK from skill_directories
        skill_dir=skill_dirs[0],
        skill_label="hiring-segment-b",
        workflow_id=input.get("workflow_id"),
        model="gpt-4.1",
    )
