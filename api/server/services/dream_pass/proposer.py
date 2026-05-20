from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from api.functions.graphs.executors.agents._wrapper import run_agent_session
from api.server.services.dream_pass.types import DreamSkill, LessonCandidate, LessonScope


@dataclass(frozen=True)
class ProposalContext:
    skill: DreamSkill
    recent_runs: list[dict[str, Any]]
    active_lessons: list[dict[str, Any]]


class LessonProposer(Protocol):
    def propose(self, ctx: ProposalContext) -> list[LessonCandidate]: ...


class StubProposer:
    """Deterministic proposer for tests and CLI smoke runs."""

    def __init__(self, *, candidates: list[tuple[str, str]]) -> None:
        self._candidates = list(candidates)

    def propose(self, ctx: ProposalContext) -> list[LessonCandidate]:
        out: list[LessonCandidate] = []
        for body, rationale in self._candidates[: ctx.skill.max_candidates_per_pass]:
            out.append(
                LessonCandidate(
                    id=str(uuid.uuid4()),
                    body=body,
                    scope=LessonScope(domain=ctx.skill.domain),
                    proposed_by=f'dream-pass:{ctx.skill.domain}:stub',
                    rationale=rationale,
                )
            )
        return out


class GHCPProposer:
    """Distill candidate lessons via run_agent_session."""

    def __init__(self, *, skill_dir: Path | None = None) -> None:
        self._skill_dir = skill_dir

    def propose(self, ctx: ProposalContext) -> list[LessonCandidate]:
        return asyncio.run(self.propose_async(ctx))

    async def propose_async(self, ctx: ProposalContext) -> list[LessonCandidate]:
        parsed = await run_agent_session(
            prompt=self._render_prompt(ctx),
            tools=[],
            skill_dir=self._skill_dir,
            skill_label=f'dream-pass-{ctx.skill.domain}',
            workflow_id=f'dream-pass:{ctx.skill.domain}',
        )
        if isinstance(parsed, list):
            items = parsed
        elif isinstance(parsed, dict):
            items = parsed.get('items') or parsed.get('candidates') or []
        else:
            items = []
        out: list[LessonCandidate] = []
        for item in items[: ctx.skill.max_candidates_per_pass]:
            if not isinstance(item, dict) or 'body' not in item:
                continue
            out.append(
                LessonCandidate(
                    id=str(uuid.uuid4()),
                    body=str(item['body']),
                    scope=LessonScope(domain=ctx.skill.domain),
                    proposed_by=f'dream-pass:{ctx.skill.domain}:ghcp',
                    rationale=str(item.get('rationale', '')),
                )
            )
        return out

    @staticmethod
    def _render_prompt(ctx: ProposalContext) -> str:
        return (
            f"You are the dream-pass agent for the '{ctx.skill.domain}' domain.\n\n"
            f"Dream-skill body:\n{ctx.skill.body}\n\n"
            f"Recent run scores:\n```json\n{json.dumps(ctx.recent_runs, indent=2)}\n```\n\n"
            f"Active lessons (do not restate):\n"
            f"```json\n{json.dumps(ctx.active_lessons, indent=2)}\n```\n\n"
            f"Return ONLY a JSON array of up to {ctx.skill.max_candidates_per_pass} objects "
            f"with keys body and rationale."
        )
