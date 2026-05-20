from __future__ import annotations

from unittest.mock import patch

import pytest

from api.server.services.dream_pass.proposer import GHCPProposer, ProposalContext, StubProposer
from api.server.services.dream_pass.types import DreamSkill


def _skill(max_candidates: int = 2) -> DreamSkill:
    return DreamSkill(
        domain='hiring',
        version='1.0',
        max_candidates_per_pass=max_candidates,
        max_experiments_per_pass=max_candidates * 3,
        body='distill recurring patterns from recent runs',
    )


def test_stub_proposer_returns_configured_candidates() -> None:
    proposer = StubProposer(
        candidates=[
            ('agency X candidates often miss step 3', 'observed in 4 recent rejections'),
            ('market UK requires extra RTW evidence', 'observed in 3 runs'),
        ]
    )
    ctx = ProposalContext(
        skill=_skill(),
        recent_runs=[{'workflow_id': 'WF-1', 'score': 0.7}],
        active_lessons=[],
    )
    candidates = proposer.propose(ctx)
    assert len(candidates) == 2
    assert candidates[0].body.startswith('agency X')
    assert candidates[0].scope.domain == 'hiring'


def test_stub_proposer_respects_max() -> None:
    proposer = StubProposer(candidates=[('a', 'r'), ('b', 'r'), ('c', 'r')])
    ctx = ProposalContext(skill=_skill(max_candidates=1), recent_runs=[], active_lessons=[])
    assert len(proposer.propose(ctx)) == 1


@pytest.mark.asyncio
async def test_ghcp_proposer_embeds_recent_runs_in_prompt() -> None:
    sent_prompts: list[str] = []

    async def fake_run(*, prompt, tools, skill_dir, skill_label, workflow_id, **kwargs):
        sent_prompts.append(prompt)
        return [
            {'body': 'distilled lesson 1', 'rationale': 'recent runs mention agency X'},
            {'body': 'distilled lesson 2', 'rationale': 'recent runs mention RTW'},
        ]

    with patch('api.server.services.dream_pass.proposer.run_agent_session', fake_run):
        proposer = GHCPProposer(skill_dir=None)
        ctx = ProposalContext(
            skill=_skill(),
            recent_runs=[
                {'workflow_id': 'WF-1', 'score': 0.7, 'note': 'agency X failed at step 3'},
                {'workflow_id': 'WF-2', 'score': 0.4, 'note': 'agency X had inconsistent dates'},
            ],
            active_lessons=[],
        )
        candidates = await proposer.propose_async(ctx)

    assert len(candidates) == 2
    assert candidates[0].body == 'distilled lesson 1'
    assert 'agency X failed at step 3' in sent_prompts[0]
