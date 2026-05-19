"""Hiring Segment F — onboarding.

Special: retry is guarded by an idempotent-only check because
`onboarding-buddy` triggers non-reversible JML / calendar / avatar
side effects. `_tool_call_summary` surfaces a flat list of
(tool_name, reversible) records the orchestrator inspects before
issuing another segment attempt.

Contract: relies on `_wrapper.run_agent_session` surfacing collected
tool calls under the `_raw_tool_calls` key on its return dict when
any tool fired. The wrapper only adds this key when there's
something to surface, keeping the shape backwards-compatible for
non-tool-using callers (Segments B/D/E).
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


_SEGMENT_F_SKILLS: list[str] = ["onboarding-buddy"]
_SEGMENT_F_MCPS: list[str] = ["avatar.render"]


class SegmentFOutput(BaseModel):
    onboarding_kickoff_id: str
    avatar_video_url: str | None = None
    day1_calendar_id: str | None = None
    provisioning_steps: list[str]


def _skills_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "server" / "skills"


def _build_segment_f_prompt(enriched: dict, prior_validator_error: str | None = None) -> str:
    schema = SegmentFOutput.model_json_schema()
    parts = [
        "You are running first-day onboarding for a hire.",
        "",
        "Context:",
        repr({k: enriched.get(k) for k in ("req_id", "candidate_id", "offer_letter_id") if k in enriched}),
        "",
        f"Available skills: {', '.join(_SEGMENT_F_SKILLS)}",
        f"Available MCPs (call as needed): {', '.join(_SEGMENT_F_MCPS)}",
        "",
        "Deliverable — return ONE JSON object matching this schema:",
        repr(schema),
        "",
        "Return only the JSON object. No preamble.",
    ]
    if prior_validator_error:
        parts.extend(["", "Previous attempt failed validation:", prior_validator_error])
    return "\n".join(parts)


def _is_reversible(tool_name: str | None) -> bool:
    """Per data/policies/tools.yaml conventions: *.list_*, *.get_*,
    *.search_*, *.lookup_*, *.query_*, *.find_*, *.check_*,
    *.resolve_* are reversible. Anything else is treated as
    irreversible (the safe default for retry gating)."""
    if not tool_name:
        return True
    safe_verbs = ("list", "get", "search", "lookup", "query", "find", "check", "resolve")
    leaf = tool_name.split(".")[-1].split("_")[0]
    return leaf in safe_verbs


async def run_segment_f(input: dict) -> dict:
    from api.functions.graphs.executors.agents._wrapper import run_agent_session
    out = await run_agent_session(
        prompt=_build_segment_f_prompt(input, prior_validator_error=input.get("prior_validator_error")),
        tools=[],
        skill_dir=_skills_dir() / "onboarding-buddy",
        skill_label="hiring-segment-f",
        workflow_id=input.get("workflow_id"),
        model="gpt-4.1",
    )
    # Surface a flat list of (tool_name, reversible) records so the
    # orchestrator (Task 4) can gate retry on whether anything
    # irreversible has already fired. `_raw_tool_calls` is only
    # present on `out` when the wrapper collected any tool calls.
    out["_tool_call_summary"] = [
        {"name": tc.get("name"), "reversible": _is_reversible(tc.get("name"))}
        for tc in (out.get("_raw_tool_calls") or [])
    ]
    return out
